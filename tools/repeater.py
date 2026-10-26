#!/usr/bin/env python3
"""Reproducible build, flash and monitor helper for the ESP32 Wi-Fi repeater.

Why this script exists
----------------------
The firmware is the upstream ``esp32_nat_router`` project, pinned as a git
submodule and never modified in place. This script turns

    pinned upstream commit + patches/*.patch + config/*  ->  firmware image

in the same way on every machine:

``prepare``
    Exports the pinned upstream commit with ``git archive`` into
    ``build/src`` and applies ``patches/*.patch``. Exporting (instead of
    patching the submodule checkout) matters on Windows: Git for Windows
    defaults to ``core.autocrlf=true``, which checks upstream out with CRLF
    line endings that LF patches do not apply to. The export is always LF.

``build``
    Validates ``config/secrets.local`` and runs ``idf.py`` for the classic
    ``esp32`` target with layered sdkconfig defaults::

        upstream sdkconfig.defaults
          -> config/sdkconfig.defaults.repeater   (tracked project overlay)
          -> config/secrets.local                 (git-ignored credentials)

    ESP-IDF only applies defaults when it creates a new sdkconfig, so the
    script regenerates the sdkconfig whenever one of these inputs changes.
    The result is copied to ``build/release/esp32`` with checksums and the
    exact esptool command taken from ESP-IDF's own ``flasher_args.json``.

``flash`` / ``monitor`` / ``erase-flash``
    Thin wrappers around ``idf.py`` that pass the same project, build
    directory and sdkconfig arguments as ``build``.

Only the Python standard library is used, so the script runs inside the
ESP-IDF Python environment without extra packages. Run it after sourcing
ESP-IDF's ``export.ps1`` / ``export.sh`` (see docs/BUILD_AND_FLASH.md).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import string
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Optional, Sequence

# --- Pinned inputs ------------------------------------------------------------
# Update UPSTREAM_COMMIT together with the submodule pointer
# (git -C upstream/esp32_nat_router checkout <sha>; git add upstream/...) and
# refresh the patches; see CONTRIBUTING.md.
UPSTREAM_COMMIT = "119e0a3d98a7c580a0fd119fde27d189cda25d39"
UPSTREAM_VERSION = "2.4.22"
REQUIRED_IDF_VERSION = "5.5.4"
IDF_TARGET = "esp32"
APP_NAME = "esp32_nat_router"

# Bump when the staging layout changes so existing build/src trees are rebuilt.
STAGING_FORMAT = "1"

REPO_ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_DIR = REPO_ROOT / "upstream" / "esp32_nat_router"
PATCH_DIR = REPO_ROOT / "patches"
CONFIG_DIR = REPO_ROOT / "config"
OVERLAY_DEFAULTS = CONFIG_DIR / "sdkconfig.defaults.repeater"
SECRETS_FILE = CONFIG_DIR / "secrets.local"
SECRETS_EXAMPLE = CONFIG_DIR / "secrets.example"
LOCKED_DEPENDENCIES = CONFIG_DIR / "dependencies.lock"

# --- Secrets ------------------------------------------------------------------
# Required: the network the board broadcasts, and the web UI login.
KEY_SSID = "CONFIG_REPEATER_SETUP_AP_SSID"
KEY_AP_PASSWORD = "CONFIG_REPEATER_SETUP_AP_PASSWORD"
KEY_ADMIN_PASSWORD = "CONFIG_REPEATER_ADMIN_PASSWORD"
# Optional (patch 0005): the existing Wi-Fi to repeat, and the board's address.
KEY_UPLINK_SSID = "CONFIG_REPEATER_UPLINK_SSID"
KEY_UPLINK_PASSWORD = "CONFIG_REPEATER_UPLINK_PASSWORD"
KEY_AP_IP = "CONFIG_REPEATER_AP_IP"
REQUIRED_KEYS = (KEY_SSID, KEY_AP_PASSWORD, KEY_ADMIN_PASSWORD)
OPTIONAL_DEFAULTS = {KEY_UPLINK_SSID: "", KEY_UPLINK_PASSWORD: "", KEY_AP_IP: "192.168.4.1"}
SECRET_KEYS = REQUIRED_KEYS + tuple(OPTIONAL_DEFAULTS)
PLACEHOLDER_MARKER = "REPLACE_ME"
DEFAULT_SETUP_SSID = "ESP32-Repeater-Setup"

# wifi_init() keeps at most 31 SSID bytes (strlcpy into a 32-byte field).
SSID_MAX_BYTES = 31
PASSWORD_MIN = 8
PASSWORD_MAX = 63
# The web login handler reads the URL-encoded password into char param[128].
LOGIN_FIELD_MAX_ENCODED = 127

_SECRET_LINE = re.compile(r'^(CONFIG_[A-Z0-9_]+)="(.*)"$')
# Characters application/x-www-form-urlencoded leaves as-is (WHATWG URL spec).
_FORM_SAFE = set(string.ascii_letters + string.digits + "*-._")


class ToolError(RuntimeError):
    """A user-facing failure: printed without a traceback."""


class SecretsError(ToolError):
    pass


def log(message: str) -> None:
    print(f"[repeater] {message}", flush=True)


# ------------------------------------------------------------------------------
# Secrets: parsing and validation (pure functions, unit-tested)
# ------------------------------------------------------------------------------

def parse_secrets(text: str) -> Dict[str, str]:
    """Parse the sdkconfig-style secrets file; optional keys get their defaults."""
    values: Dict[str, str] = {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _SECRET_LINE.match(line)
        if not match:
            raise SecretsError(f'line {lineno}: expected CONFIG_NAME="value"')
        key, value = match.groups()
        if key not in SECRET_KEYS:
            raise SecretsError(
                f"line {lineno}: unknown key {key} (allowed: {', '.join(SECRET_KEYS)})"
            )
        if key in values:
            raise SecretsError(f"line {lineno}: {key} is set twice")
        values[key] = value
    missing = [key for key in REQUIRED_KEYS if key not in values]
    if missing:
        raise SecretsError(f"missing keys: {', '.join(missing)}")
    return {**OPTIONAL_DEFAULTS, **values}


def form_encoded_length(value: str) -> int:
    """Length of ``value`` after a browser form-encodes it."""
    length = 0
    for char in value:
        if char in _FORM_SAFE or char == " ":
            length += 1  # space becomes '+'
        else:
            length += 3 * len(char.encode("utf-8"))
    return length


_TRIGRAPH = re.compile(r"\?\?[=(/)'<!>-]")


def _check_quoting(label: str, value: str) -> List[str]:
    """Reject characters that would not survive sdkconfig -> sdkconfig.h -> C."""
    errors: List[str] = []
    # '"' and '\' need escaping in sdkconfig files; refusing them avoids an
    # entire class of quoting bugs between this file, Kconfig and C.
    if '"' in value or "\\" in value:
        errors.append(f'{label}: must not contain a double quote (") or backslash (\\)')
    # The value becomes a C string literal. ESP-IDF builds with -std=gnu17
    # -Werror=all, so a trigraph such as "??(" fails with -Werror=trigraphs.
    if _TRIGRAPH.search(value):
        errors.append(f"{label}: must not contain '??' followed by one of = ( / ) ' < ! > - "
                      "(a C trigraph, which breaks the build)")
    return errors


def _check_password(label: str, value: str) -> List[str]:
    errors: List[str] = []
    if PLACEHOLDER_MARKER in value:
        return [f"{label}: still contains the {PLACEHOLDER_MARKER} placeholder"]
    if not PASSWORD_MIN <= len(value) <= PASSWORD_MAX:
        errors.append(f"{label}: must be {PASSWORD_MIN}-{PASSWORD_MAX} characters (got {len(value)})")
    if any(not 0x20 <= ord(char) <= 0x7E for char in value):
        errors.append(f"{label}: only printable ASCII characters are allowed")
    if value != value.strip():
        errors.append(f"{label}: must not start or end with a space")
    errors.extend(_check_quoting(label, value))
    return errors


def _check_ssid(label: str, value: str, allow_empty: bool) -> List[str]:
    errors: List[str] = []
    size = len(value.encode("utf-8"))
    if PLACEHOLDER_MARKER in value:
        return [f"{label}: still contains the {PLACEHOLDER_MARKER} placeholder"]
    low = 0 if allow_empty else 1
    if not low <= size <= SSID_MAX_BYTES:
        errors.append(f"{label}: must be {low}-{SSID_MAX_BYTES} bytes (got {size})")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in value):
        errors.append(f"{label}: must not contain control characters")
    if value != value.strip():
        errors.append(f"{label}: must not start or end with whitespace")
    errors.extend(_check_quoting(label, value))
    return errors


def ap_ip_is_valid(value: str) -> bool:
    """Same rules as ap_ip_is_valid() in the firmware (patch 0003): strict dotted
    quad, unicast, and a usable host address in the /24 the AP always uses."""
    parts = value.split(".")
    if len(parts) != 4 or not all(p.isdigit() and p.isascii() and 1 <= len(p) <= 3 for p in parts):
        return False
    octets = [int(p) for p in parts]
    if any(o > 255 for o in octets):
        return False
    if octets[0] in (0, 127) or octets[0] >= 224 or octets[:2] == [169, 254]:
        return False
    return 1 <= octets[3] <= 254


def validate_secrets(values: Dict[str, str]) -> List[str]:
    """Return a list of human-readable problems (empty when valid)."""
    values = {**OPTIONAL_DEFAULTS, **values}
    errors: List[str] = []

    ssid = values[KEY_SSID]
    errors.extend(_check_ssid(KEY_SSID, ssid, allow_empty=False))

    ap_password = values[KEY_AP_PASSWORD]
    admin_password = values[KEY_ADMIN_PASSWORD]
    errors.extend(_check_password(KEY_AP_PASSWORD, ap_password))
    admin_errors = _check_password(KEY_ADMIN_PASSWORD, admin_password)
    errors.extend(admin_errors)
    if not admin_errors and form_encoded_length(admin_password) > LOGIN_FIELD_MAX_ENCODED:
        errors.append(
            f"{KEY_ADMIN_PASSWORD}: too many symbols; the web login accepts at most "
            f"{LOGIN_FIELD_MAX_ENCODED} URL-encoded bytes "
            f"(this one encodes to {form_encoded_length(admin_password)})"
        )
    if ap_password == admin_password:
        errors.append(
            f"{KEY_ADMIN_PASSWORD}: must differ from {KEY_AP_PASSWORD}; everyone who "
            "joins the Wi-Fi would otherwise be able to reconfigure the router"
        )

    uplink_ssid = values[KEY_UPLINK_SSID]
    uplink_password = values[KEY_UPLINK_PASSWORD]
    errors.extend(_check_ssid(KEY_UPLINK_SSID, uplink_ssid, allow_empty=True))
    if uplink_password:
        if not uplink_ssid:
            errors.append(f"{KEY_UPLINK_PASSWORD}: is set but {KEY_UPLINK_SSID} is empty")
        # WPA passphrase rules; an empty password means an open network.
        errors.extend(_check_password(KEY_UPLINK_PASSWORD, uplink_password))
    if uplink_ssid and uplink_ssid == ssid:
        errors.append(
            f"{KEY_SSID}: must differ from {KEY_UPLINK_SSID}; the repeater network is a "
            "separate network and devices would confuse the two"
        )

    ap_ip = values[KEY_AP_IP]
    if not ap_ip_is_valid(ap_ip):
        errors.append(
            f"{KEY_AP_IP}: '{ap_ip}' is not usable; give a dotted-quad address whose last "
            "number is 1-254, e.g. 192.168.4.1 (a second board: 192.168.5.1)"
        )
    return errors


def generate_password(groups: int, alphabet: str = string.ascii_lowercase + string.digits) -> str:
    """Random, easy-to-type password such as 'k3fp-9xq2-m7aa-04zt'."""
    return "-".join(
        "".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(groups)
    )


def render_secrets(ssid: str, ap_password: str, admin_password: str) -> str:
    return (
        "# Generated by `python tools/repeater.py init-secrets`. Git-ignored: never commit.\n"
        "# Every value is explained in config/secrets.example and docs/FLASHING_GUIDE.md.\n"
        "\n"
        "# The Wi-Fi network the repeater broadcasts (phones and laptops join this one).\n"
        f'{KEY_SSID}="{ssid}"\n'
        f'{KEY_AP_PASSWORD}="{ap_password}"\n'
        "\n"
        "# Login for the web page at http://192.168.4.1 (keep it different from Wi-Fi passwords).\n"
        f'{KEY_ADMIN_PASSWORD}="{admin_password}"\n'
        "\n"
        "# Optional: the existing Wi-Fi to repeat. Remove the leading '# ' and fill in\n"
        "# both lines to connect automatically on first boot; otherwise enter it later\n"
        "# on the Getting Started page. Leave the password empty for an open network.\n"
        f'# {KEY_UPLINK_SSID}="{PLACEHOLDER_MARKER}_existing_wifi_name"\n'
        f'# {KEY_UPLINK_PASSWORD}="{PLACEHOLDER_MARKER}_existing_wifi_password"\n'
        "\n"
        "# Optional: the repeater's own address. Change only for a second board that\n"
        "# connects to the first one (use 192.168.5.1 there).\n"
        f'# {KEY_AP_IP}="192.168.4.1"\n'
    )


def load_secrets(path: Optional[Path] = None) -> Dict[str, str]:
    path = path or SECRETS_FILE
    if not path.is_file():
        raise SecretsError(
            f"{_rel(path)} not found. Create it with\n"
            "    python tools/repeater.py init-secrets\n"
            f"or copy {_rel(SECRETS_EXAMPLE)} and replace every {PLACEHOLDER_MARKER} value."
        )
    values = parse_secrets(path.read_text(encoding="utf-8"))
    errors = validate_secrets(values)
    if errors:
        raise SecretsError(f"{_rel(path)} is invalid:\n  - " + "\n  - ".join(errors))
    return values


# ------------------------------------------------------------------------------
# Paths and process helpers
# ------------------------------------------------------------------------------

def build_root() -> Path:
    """Build directory; REPEATER_BUILD_DIR relocates it (e.g. off a path with spaces)."""
    override = os.environ.get("REPEATER_BUILD_DIR")
    return Path(override).resolve() if override else REPO_ROOT / "build"


def src_dir() -> Path:
    return build_root() / "src"


def bin_dir() -> Path:
    return build_root() / IDF_TARGET


def sdkconfig_path() -> Path:
    return build_root() / f"sdkconfig.{IDF_TARGET}"


def release_dir() -> Path:
    return build_root() / "release" / IDF_TARGET


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _git_env() -> Dict[str, str]:
    env = os.environ.copy()
    # Variables set by git hooks or wrappers would point git at the wrong repo.
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(name, None)
    return env


def _idf_env() -> Dict[str, str]:
    """Environment for idf.py: every git process it starts checks out with LF.

    The ESP-IDF component manager fetches esp_wireguard with git and verifies it
    against the component_hash in dependencies.lock, a hash over the checked-out
    bytes. Git for Windows defaults to core.autocrlf=true, so a Windows checkout
    (CRLF) hashes differently from Linux (LF) and the pinned lock fails on the
    other OS ("The downloaded component ... is corrupted"). GIT_CONFIG_COUNT
    (git >= 2.31) overrides the setting without touching any git config file.
    """
    env = _git_env()
    count = int(env.get("GIT_CONFIG_COUNT") or 0)
    for key, value in (("core.autocrlf", "false"), ("core.eol", "lf")):
        env[f"GIT_CONFIG_KEY_{count}"] = key
        env[f"GIT_CONFIG_VALUE_{count}"] = value
        count += 1
    env["GIT_CONFIG_COUNT"] = str(count)
    return env


def run(cmd: Sequence[str], cwd: Optional[Path] = None, check: bool = True,
        capture: bool = False, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    try:
        proc = subprocess.run(
            list(cmd), cwd=str(cwd) if cwd else None, env=env or _git_env(),
            capture_output=capture, text=capture,
        )
    except FileNotFoundError as error:
        raise ToolError(f"'{cmd[0]}' was not found; is it installed and on PATH?") from error
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip() if capture else ""
        raise ToolError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{detail}".rstrip())
    return proc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


BUILD_MARKER = ".repeater-build-root"


def remove_tree(path: Path, expected_parent: Path) -> None:
    """rmtree with a guard: only deletes a direct child of ``expected_parent``."""
    path = path.resolve()
    if str(path) == path.anchor or path.parent != expected_parent.resolve():
        raise ToolError(f"refusing to delete unexpected path {path}")
    try:
        shutil.rmtree(path)
    except OSError as error:
        # Typical on Windows: a terminal, editor or monitor still has the
        # directory (or a file in it) open.
        raise ToolError(
            f"cannot delete {path}: {error.strerror or error}. Close any terminal, editor "
            "or serial monitor using it and retry."
        ) from error


# ------------------------------------------------------------------------------
# ESP-IDF environment
# ------------------------------------------------------------------------------

def read_idf_version(idf_path: Path) -> str:
    version_file = idf_path / "tools" / "cmake" / "version.cmake"
    if not version_file.is_file():
        raise ToolError(f"{version_file} not found; is IDF_PATH an ESP-IDF checkout?")
    text = version_file.read_text(encoding="utf-8")
    parts = []
    for name in ("MAJOR", "MINOR", "PATCH"):
        match = re.search(rf"IDF_VERSION_{name}\s+(\d+)", text)
        if not match:
            raise ToolError(f"cannot read IDF_VERSION_{name} from {version_file}")
        parts.append(match.group(1))
    return ".".join(parts)


def idf_environment(allow_mismatch: bool) -> Dict[str, object]:
    idf_path_env = os.environ.get("IDF_PATH")
    if not idf_path_env:
        raise ToolError(
            "IDF_PATH is not set. Open a terminal, run ESP-IDF v"
            f"{REQUIRED_IDF_VERSION}'s export script, then rerun this command:\n"
            "    PowerShell:  C:\\Users\\<you>\\esp\\v5.5.4\\esp-idf\\export.ps1\n"
            "    bash/zsh:    . ~/esp/v5.5.4/esp-idf/export.sh\n"
            "See docs/BUILD_AND_FLASH.md."
        )
    idf_path = Path(idf_path_env)
    version = read_idf_version(idf_path)
    if version != REQUIRED_IDF_VERSION:
        message = (
            f"ESP-IDF {version} is active but this project is pinned to {REQUIRED_IDF_VERSION} "
            "(the version upstream builds its release binaries with)."
        )
        if not allow_mismatch:
            raise ToolError(message + " Pass --allow-idf-mismatch to try anyway.")
        log("WARNING: " + message)

    # Prefer the ESP-IDF virtualenv's interpreter: idf.py needs its packages.
    python = Path(sys.executable)
    venv = os.environ.get("IDF_PYTHON_ENV_PATH")
    if venv:
        candidate = Path(venv) / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if candidate.is_file():
            python = candidate
    return {"path": idf_path, "version": version, "python": python}


def idf_command(env: Dict[str, object], *actions: str, extra: Sequence[str] = ()) -> List[str]:
    defaults = [src_dir() / "sdkconfig.defaults", OVERLAY_DEFAULTS, SECRETS_FILE]
    return [
        str(env["python"]), str(Path(env["path"]) / "tools" / "idf.py"),
        "-C", str(src_dir()),
        "-B", str(bin_dir()),
        f"-DIDF_TARGET={IDF_TARGET}",
        f"-DSDKCONFIG={sdkconfig_path().as_posix()}",
        "-DSDKCONFIG_DEFAULTS=" + ";".join(p.as_posix() for p in defaults),
        *extra,
        *actions,
    ]


# ------------------------------------------------------------------------------
# Upstream staging
# ------------------------------------------------------------------------------

def list_patches() -> List[Path]:
    return sorted(PATCH_DIR.glob("*.patch"))


def source_stamp(patches: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    digest.update(f"format={STAGING_FORMAT}\ncommit={UPSTREAM_COMMIT}\n".encode())
    for patch in patches:
        digest.update(patch.name.encode() + b"\0" + patch.read_bytes() + b"\0")
    if LOCKED_DEPENDENCIES.is_file():
        digest.update(b"lock\0" + LOCKED_DEPENDENCIES.read_bytes())
    return digest.hexdigest()


def is_safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and not name.startswith(("/", "\\"))


SUBMODULE_PATH = "upstream/esp32_nat_router"


def submodule_index_mode() -> Optional[str]:
    """Git file mode of the upstream path in the project index ("160000" = submodule)."""
    out = run(["git", "-C", str(REPO_ROOT), "ls-files", "--stage", "--", SUBMODULE_PATH],
              check=False, capture=True).stdout
    lines = out.splitlines()
    return lines[0].split()[0] if lines else None


def ensure_upstream_available() -> None:
    if (REPO_ROOT / ".git").exists():
        mode = submodule_index_mode()
        if mode is not None and mode != "160000":
            # Seen when the project's .git folder is recreated: the submodule's
            # .git pointer dangles and `git add` commits upstream as plain files.
            raise ToolError(
                f"{SUBMODULE_PATH} is tracked as ordinary files, not as a git submodule, so the "
                "pinned upstream history is not available. Convert it back and commit:\n"
                f"    git rm -r -q --cached {SUBMODULE_PATH}\n"
                f"    (move the {SUBMODULE_PATH} folder out of the repository)\n"
                f"    git submodule add https://github.com/martin-ger/esp32_nat_router.git {SUBMODULE_PATH}\n"
                f"    git -C {SUBMODULE_PATH} checkout {UPSTREAM_COMMIT}\n"
                f"    git add {SUBMODULE_PATH}"
            )
    if not (UPSTREAM_DIR / ".git").exists():
        if not (REPO_ROOT / ".git").exists():
            raise ToolError(
                f"{REPO_ROOT} is not a git clone, so the upstream submodule cannot be fetched "
                "(GitHub ZIP downloads omit submodules). Clone with: git clone --recursive <url>"
            )
        log("initialising the upstream submodule")
        run(["git", "-C", str(REPO_ROOT), "submodule", "update", "--init", "--", SUBMODULE_PATH])
    probe = run(["git", "-C", str(UPSTREAM_DIR), "cat-file", "-e", f"{UPSTREAM_COMMIT}^{{commit}}"],
                check=False, capture=True)
    if probe.returncode != 0:
        raise ToolError(
            f"upstream commit {UPSTREAM_COMMIT[:12]} is not available in {_rel(UPSTREAM_DIR)}.\n"
            "Run: git submodule update --init --recursive"
        )


def export_upstream(destination: Path) -> None:
    # core.autocrlf=false: the archive must contain the committed LF bytes.
    try:
        archive = subprocess.run(
            ["git", "-C", str(UPSTREAM_DIR), "-c", "core.autocrlf=false", "-c", "core.eol=lf",
             "archive", "--format=tar", UPSTREAM_COMMIT],
            capture_output=True, env=_git_env(),
        )
    except FileNotFoundError as error:
        raise ToolError("'git' was not found; is it installed and on PATH?") from error
    if archive.returncode != 0:
        raise ToolError("git archive failed: " + archive.stderr.decode(errors="replace"))
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        members = tar.getmembers()
        unsafe = [m.name for m in members if not is_safe_member(m.name)]
        if unsafe:
            raise ToolError(f"refusing unsafe paths in upstream archive: {unsafe[:3]}")
        if hasattr(tarfile, "data_filter"):
            tar.extractall(destination, filter="data")
        else:  # Python < 3.11.4: members were validated above
            tar.extractall(destination, members=[m for m in members if m.isfile() or m.isdir()])


def prepare(force: bool = False) -> Path:
    root = build_root()
    src = src_dir()
    patches = list_patches()
    stamp = source_stamp(patches)
    stamp_file = root / "src.stamp"
    if (not force and src.is_dir() and stamp_file.is_file()
            and stamp_file.read_text(encoding="utf-8").strip() == stamp):
        log(f"upstream sources up to date in {_rel(src)}")
        return src

    ensure_upstream_available()
    root.mkdir(parents=True, exist_ok=True)
    # Lets `clean` prove the directory is ours before deleting it.
    (root / BUILD_MARKER).touch()
    if src.exists():
        remove_tree(src, root)
    src.mkdir()
    log(f"exporting upstream {UPSTREAM_COMMIT[:12]} (v{UPSTREAM_VERSION}) to {_rel(src)}")
    export_upstream(src)

    # A repository of its own makes `git apply` resolve paths relative to
    # build/src instead of the enclosing project repository.
    run(["git", "init", "-q"], cwd=src)
    # Otherwise a system-wide core.autocrlf=true makes `git apply` write CRLF.
    run(["git", "config", "core.autocrlf", "false"], cwd=src)
    run(["git", "config", "core.eol", "lf"], cwd=src)
    for patch in patches:
        check = run(["git", "apply", "--check", str(patch)], cwd=src, check=False, capture=True)
        if check.returncode != 0:
            raise ToolError(
                f"{patch.name} does not apply to upstream {UPSTREAM_COMMIT[:12]}:\n"
                f"{check.stderr.strip()}\nRefresh the patch (see CONTRIBUTING.md)."
            )
        run(["git", "apply", "--whitespace=nowarn", str(patch)], cwd=src)
        log(f"applied {patch.name}")

    if LOCKED_DEPENDENCIES.is_file():
        shutil.copy2(LOCKED_DEPENDENCIES, src / "dependencies.lock")
        log(f"using pinned component versions from {_rel(LOCKED_DEPENDENCIES)}")

    stamp_file.write_text(stamp + "\n", encoding="utf-8")
    return src


def refresh_sdkconfig_if_inputs_changed(idf_version: str) -> None:
    """ESP-IDF ignores sdkconfig defaults once an sdkconfig exists; regenerate it."""
    digest = hashlib.sha256(f"idf={idf_version}\ntarget={IDF_TARGET}\n".encode())
    for path in (src_dir() / "sdkconfig.defaults", OVERLAY_DEFAULTS, SECRETS_FILE):
        digest.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    stamp = digest.hexdigest()
    stamp_file = build_root() / "sdkconfig.stamp"
    if stamp_file.is_file() and stamp_file.read_text(encoding="utf-8").strip() == stamp:
        return
    removed = False
    for stale in (sdkconfig_path(), Path(str(sdkconfig_path()) + ".old"), bin_dir() / "CMakeCache.txt"):
        if stale.is_file():
            stale.unlink()
            removed = True
    if removed:
        log("configuration inputs changed: sdkconfig will be regenerated")
    stamp_file.parent.mkdir(parents=True, exist_ok=True)
    stamp_file.write_text(stamp + "\n", encoding="utf-8")


# ------------------------------------------------------------------------------
# Release artifacts
# ------------------------------------------------------------------------------

def parse_partition_size(text: str, name: str) -> Optional[int]:
    for line in text.splitlines():
        fields = [field.strip() for field in line.split("#", 1)[0].split(",")]
        if len(fields) >= 5 and fields[0] == name:
            size = fields[4].upper()
            multiplier = 1
            if size.endswith("K"):
                multiplier, size = 1024, size[:-1]
            elif size.endswith("M"):
                multiplier, size = 1024 * 1024, size[:-1]
            return int(size, 0) * multiplier
    return None


def collect_release(idf_version: str) -> Path:
    flasher_args_file = bin_dir() / "flasher_args.json"
    flasher_args = json.loads(flasher_args_file.read_text(encoding="utf-8"))
    out = release_dir()
    if out.exists():
        remove_tree(out, out.parent)
    out.mkdir(parents=True)

    images = []
    for offset, relative in sorted(flasher_args["flash_files"].items(), key=lambda kv: int(kv[0], 16)):
        source = bin_dir() / relative
        target = out / Path(relative).name
        shutil.copy2(source, target)
        images.append((offset, target))

    settings = flasher_args["flash_settings"]
    extra = flasher_args.get("extra_esptool_args", {})
    command = [
        "python", "-m", "esptool", "--chip", extra.get("chip", IDF_TARGET), "-p", "<PORT>",
        "-b", "460800", "--before", extra.get("before", "default_reset"),
        "--after", extra.get("after", "hard_reset"), "write_flash",
        "--flash_mode", settings["flash_mode"], "--flash_freq", settings["flash_freq"],
        "--flash_size", settings["flash_size"],
    ]
    for offset, path in images:
        command += [offset, path.name]
    (out / "flash_command.txt").write_text(
        "# Run from this directory. Offsets and flash settings come from ESP-IDF's\n"
        "# flasher_args.json for this exact build.\n" + " ".join(command) + "\n",
        encoding="utf-8",
    )

    app = out / f"{APP_NAME}.bin"
    partitions_csv = (src_dir() / "partitions_example.csv").read_text(encoding="utf-8")
    slot = parse_partition_size(partitions_csv, "ota_0")
    app_size = app.stat().st_size
    info = {
        "target": IDF_TARGET,
        "board": "ESP32 DevKit V1 (ESP-WROOM-32, 4 MB flash)",
        "upstream_repository": "https://github.com/martin-ger/esp32_nat_router",
        "upstream_commit": UPSTREAM_COMMIT,
        "upstream_version": UPSTREAM_VERSION,
        "esp_idf_version": idf_version,
        "patches": {p.name: sha256_file(p) for p in list_patches()},
        "built_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "app_image_bytes": app_size,
        "ota_slot_bytes": slot,
        "ota_slot_used_percent": round(100.0 * app_size / slot, 1) if slot else None,
        "flash_files": {offset: path.name for offset, path in images},
    }
    (out / "build_info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    sums = "".join(f"{sha256_file(p)}  {p.name}\n" for _, p in images)
    (out / "SHA256SUMS").write_text(sums, encoding="utf-8")
    (out / "PRIVATE-DO-NOT-SHARE.txt").write_text(
        "These images embed the setup AP and admin passwords from config/secrets.local.\n"
        "Do not upload, attach or share them. Rebuild with fresh secrets for anyone else.\n",
        encoding="utf-8",
    )
    if slot:
        log(f"app image {app_size} bytes = {info['ota_slot_used_percent']}% of the {slot}-byte OTA slot")
    return out


def update_dependency_lock() -> None:
    generated = src_dir() / "dependencies.lock"
    if not generated.is_file():
        return
    if not LOCKED_DEPENDENCIES.is_file():
        shutil.copy2(generated, LOCKED_DEPENDENCIES)
        log(f"recorded component versions in {_rel(LOCKED_DEPENDENCIES)}; commit it")
    elif generated.read_bytes() != LOCKED_DEPENDENCIES.read_bytes():
        log(f"WARNING: managed component versions differ from {_rel(LOCKED_DEPENDENCIES)}; "
            "review build/src/dependencies.lock and copy it over if the change is intended")


# ------------------------------------------------------------------------------
# Commands
# ------------------------------------------------------------------------------

def warn_if_not_ignored(path: Path) -> None:
    """Secrets files must never be committed; *.local names are git-ignored."""
    probe = run(["git", "-C", str(REPO_ROOT), "check-ignore", "-q", "--", str(path)],
                check=False, capture=True)
    if probe.returncode == 1:
        log(f"WARNING: {_rel(path)} is NOT git-ignored and could be committed. "
            "Name secrets files *.local (e.g. config/board2.local).")


def run_idf(env: Dict[str, object], *actions: str, extra: Sequence[str] = ()) -> int:
    return run(idf_command(env, *actions, extra=extra), check=False, env=_idf_env()).returncode


def cmd_check_secrets(args: argparse.Namespace) -> int:
    path = Path(args.file).resolve() if args.file else SECRETS_FILE
    load_secrets(path)
    log(f"{_rel(path)} is valid")
    return 0


def cmd_init_secrets(args: argparse.Namespace) -> int:
    if SECRETS_FILE.exists() and not args.force:
        raise ToolError(f"{_rel(SECRETS_FILE)} already exists (use --force to replace it)")
    values = {
        KEY_SSID: args.ssid,
        KEY_AP_PASSWORD: generate_password(groups=4),
        KEY_ADMIN_PASSWORD: generate_password(groups=5),
    }
    errors = validate_secrets(values)
    if errors:
        raise SecretsError("\n".join(errors))
    SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SECRETS_FILE.write_text(
        render_secrets(values[KEY_SSID], values[KEY_AP_PASSWORD], values[KEY_ADMIN_PASSWORD]),
        encoding="utf-8",
    )
    log(f"wrote {_rel(SECRETS_FILE)} with random passwords (not printed here).")
    log("Open the file to read them, and optionally add the Wi-Fi to repeat "
        "(see docs/FLASHING_GUIDE.md, step 4).")
    warn_if_not_ignored(SECRETS_FILE)
    return 0


def cmd_prepare(args: argparse.Namespace) -> int:
    prepare(force=args.force)
    return 0


def _prepare_build(args: argparse.Namespace) -> Dict[str, object]:
    values = load_secrets()
    warn_if_not_ignored(SECRETS_FILE)
    env = idf_environment(args.allow_idf_mismatch)
    log(f"ESP-IDF {env['version']} at {env['path']}")
    if SECRETS_FILE != CONFIG_DIR / "secrets.local":
        log(f"using secrets from {_rel(SECRETS_FILE)}")
    if values[KEY_UPLINK_SSID]:
        log(f"build-time uplink '{values[KEY_UPLINK_SSID]}'; repeater network "
            f"'{values[KEY_SSID]}' on {values[KEY_AP_IP]}")
    else:
        log(f"no build-time uplink: choose the Wi-Fi to repeat at http://{values[KEY_AP_IP]} after flashing")
    prepare()
    refresh_sdkconfig_if_inputs_changed(str(env["version"]))
    return env


def cmd_build(args: argparse.Namespace) -> int:
    env = _prepare_build(args)
    code = run_idf(env, "build")
    if code != 0:
        log(f"idf.py build failed with exit code {code}")
        return code
    update_dependency_lock()
    out = collect_release(str(env["version"]))
    log(f"release images for {IDF_TARGET}: {_rel(out)}")
    return 0


def _port_args(args: argparse.Namespace) -> List[str]:
    extra = ["-p", args.port]
    if getattr(args, "baud", None):
        extra += ["-b", str(args.baud)]
    return extra


def cmd_flash(args: argparse.Namespace) -> int:
    env = _prepare_build(args)
    actions = ["flash"]
    if args.erase:
        # idf.py runs erase-flash before flash (order_dependencies of "flash").
        log("--erase: wiping the whole flash first, including all saved settings")
        actions.insert(0, "erase-flash")
    if args.monitor:
        actions.append("monitor")
    return run_idf(env, *actions, extra=_port_args(args))


def cmd_monitor(args: argparse.Namespace) -> int:
    env = idf_environment(args.allow_idf_mismatch)
    if not (bin_dir() / "CMakeCache.txt").is_file():
        raise ToolError("nothing built yet; run `python tools/repeater.py build` first")
    return run_idf(env, "monitor", extra=["-p", args.port])


def cmd_erase_flash(args: argparse.Namespace) -> int:
    if not args.yes:
        raise ToolError("erase-flash wipes firmware AND all settings (NVS). Re-run with --yes to confirm.")
    env = idf_environment(args.allow_idf_mismatch)
    prepare()
    return run_idf(env, "erase-flash", extra=["-p", args.port])


def cmd_info(args: argparse.Namespace) -> int:
    print(f"upstream        {UPSTREAM_COMMIT} (v{UPSTREAM_VERSION})")
    print(f"ESP-IDF         {REQUIRED_IDF_VERSION} (required)")
    print(f"target          {IDF_TARGET}")
    print(f"patches         {', '.join(p.name for p in list_patches()) or '(none)'}")
    print(f"build root      {build_root()}")
    print(f"secrets file    {SECRETS_FILE} ({'present' if SECRETS_FILE.is_file() else 'missing'})")
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    root = build_root()
    if not root.exists():
        return 0
    if not (root / BUILD_MARKER).is_file():
        raise ToolError(f"{root} was not created by this tool ({BUILD_MARKER} missing); not deleting it")
    remove_tree(root, root.parent)
    log(f"removed {root}")
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repeater.py",
        description="Build, flash and monitor the ESP32 DevKit V1 Wi-Fi repeater firmware.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Shared by every command so that --secrets works with all of them.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--secrets", metavar="FILE",
                        help="secrets file to use instead of config/secrets.local "
                             "(e.g. config/board2.local for a second board)")

    def with_idf(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
        p.add_argument("--allow-idf-mismatch", action="store_true",
                       help=f"continue when the active ESP-IDF is not v{REQUIRED_IDF_VERSION}")
        return p

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        return sub.add_parser(name, help=help_text, parents=[common])

    p = add("init-secrets", "create a secrets file with random passwords")
    p.add_argument("--ssid", default=DEFAULT_SETUP_SSID, help="name of the network the repeater broadcasts")
    p.add_argument("--force", action="store_true", help="overwrite an existing secrets file")
    p.set_defaults(func=cmd_init_secrets)

    p = add("check-secrets", "validate the secrets file")
    p.add_argument("--file", help="validate this file (same as --secrets)")
    p.set_defaults(func=cmd_check_secrets)

    p = add("prepare", "export pinned upstream and apply patches")
    p.add_argument("--force", action="store_true", help="re-export even if up to date")
    p.set_defaults(func=cmd_prepare)

    with_idf(add("build", "build firmware for the classic ESP32")).set_defaults(func=cmd_build)

    p = with_idf(add("flash", "build if needed and flash over USB"))
    p.add_argument("-p", "--port", required=True, help="serial port, e.g. COM5 or /dev/ttyUSB0")
    p.add_argument("-b", "--baud", type=int, help="flash baud rate (ESP-IDF default 460800)")
    p.add_argument("--monitor", action="store_true", help="open the serial monitor afterwards")
    p.add_argument("--erase", action="store_true",
                   help="erase the whole flash first (wipes saved settings, so the values in "
                        "the secrets file apply again)")
    p.set_defaults(func=cmd_flash)

    p = with_idf(add("monitor", "open the serial monitor (115200 baud)"))
    p.add_argument("-p", "--port", required=True)
    p.set_defaults(func=cmd_monitor)

    p = with_idf(add("erase-flash", "erase the whole flash chip (firmware + settings)"))
    p.add_argument("-p", "--port", required=True)
    p.add_argument("--yes", action="store_true", help="confirm the erase")
    p.set_defaults(func=cmd_erase_flash)

    add("info", "show pinned versions and paths").set_defaults(func=cmd_info)
    add("clean", "delete the build directory").set_defaults(func=cmd_clean)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    global SECRETS_FILE
    args = make_parser().parse_args(argv)
    original = SECRETS_FILE
    if getattr(args, "secrets", None):
        SECRETS_FILE = Path(args.secrets).resolve()
    try:
        return args.func(args)
    except ToolError as error:
        print(f"[repeater] ERROR: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    finally:
        SECRETS_FILE = original


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Compile and run the host C unit tests against the patched upstream sources.

The tests include headers from build/src (created by
``python tools/repeater.py prepare``), so they exercise exactly the code that
goes into the firmware. A host compiler is located in this order:

1. ``$CC`` or ``cc`` / ``gcc`` / ``clang`` on PATH (Linux, macOS, CI);
2. Microsoft C/C++ via ``vswhere`` (Windows with Visual Studio Build Tools).

Warnings are errors with every compiler. Exit code 0 means all checks passed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = Path(os.environ["REPEATER_BUILD_DIR"]).resolve() if os.environ.get("REPEATER_BUILD_DIR") \
    else REPO_ROOT / "build"
INCLUDE_DIR = BUILD_ROOT / "src" / "components" / "cmd_router"
OUT_DIR = BUILD_ROOT / "host-tests"
TESTS = [Path(__file__).with_name("test_input_validation.c")]


def find_unix_compiler() -> Optional[str]:
    for name in (os.environ.get("CC"), "cc", "gcc", "clang"):
        if name and shutil.which(name):
            return shutil.which(name)
    return None


VSWHERE = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / \
    "Microsoft Visual Studio" / "Installer" / "vswhere.exe"


def find_msvc_vcvars() -> Optional[Path]:
    vswhere = VSWHERE
    if not vswhere.is_file():
        return None
    result = subprocess.run(
        [str(vswhere), "-latest", "-products", "*",
         "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
         "-property", "installationPath"],
        capture_output=True, text=True,
    )
    for line in result.stdout.splitlines():
        vcvars = Path(line.strip()) / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
        if vcvars.is_file():
            return vcvars
    return None


def compile_test(source: Path) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cc = find_unix_compiler()
    if cc:
        exe = OUT_DIR / source.stem
        cmd: List[str] = [cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic",
                          "-I", str(INCLUDE_DIR), str(source), "-o", str(exe)]
        print("$ " + " ".join(cmd), flush=True)
        subprocess.run(cmd, check=True)
        return exe
    vcvars = find_msvc_vcvars() if os.name == "nt" else None
    if vcvars:
        exe = OUT_DIR / f"{source.stem}.exe"
        # cwd=OUT_DIR keeps .obj files out of the source tree; /s strips only
        # the outer quotes so the quoted paths with spaces survive cmd.exe.
        inner = (f'call "{vcvars}" >nul && cl /nologo /W4 /WX /std:c11 '
                 f'/I "{INCLUDE_DIR}" "{source}" /Fe:"{exe.name}"')
        print(f"$ {inner}", flush=True)
        env = os.environ.copy()
        # vcvars64.bat calls vswhere by name; without this it prints a warning.
        env["PATH"] = str(VSWHERE.parent) + os.pathsep + env.get("PATH", "")
        subprocess.run(f'cmd /s /c "{inner}"', check=True, cwd=str(OUT_DIR), env=env)
        return exe
    raise SystemExit("no host C compiler found (install gcc/clang, or Visual Studio Build Tools)")


def main() -> int:
    if not (INCLUDE_DIR / "input_validation.h").is_file():
        print("build/src is missing; run `python tools/repeater.py prepare` first", file=sys.stderr)
        return 2
    failed = 0
    for source in TESTS:
        exe = compile_test(source)
        result = subprocess.run([str(exe)])
        failed += 1 if result.returncode != 0 else 0
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

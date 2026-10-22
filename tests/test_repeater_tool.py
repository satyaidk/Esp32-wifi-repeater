"""Unit tests for tools/repeater.py (standard library only).

Run from the repository root:

    python -m unittest discover -s tests -v

The tests cover the parts that decide whether a firmware image is safe to
produce: secrets parsing and validation, password generation, archive path
checks, partition parsing and the deletion guard. Building and flashing need
ESP-IDF and hardware and are covered by docs/TEST_PLAN.md instead.
"""

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

import repeater  # noqa: E402  (import after sys.path setup)
from repeater import (  # noqa: E402
    KEY_ADMIN_PASSWORD,
    KEY_AP_PASSWORD,
    KEY_SSID,
    SecretsError,
    ToolError,
    form_encoded_length,
    generate_password,
    is_safe_member,
    parse_partition_size,
    parse_secrets,
    remove_tree,
    render_secrets,
    validate_secrets,
)


def valid_values(**overrides):
    values = {
        KEY_SSID: "ESP32-Repeater-Setup",
        KEY_AP_PASSWORD: "wifi-pass-1234",
        KEY_ADMIN_PASSWORD: "admin-pass-5678",
    }
    values.update(overrides)
    return values


class ParseSecretsTest(unittest.TestCase):
    def test_parses_all_keys_and_ignores_comments(self):
        text = (
            "# comment\n\n"
            f'{KEY_SSID}="Setup Net"\n'
            f'{KEY_AP_PASSWORD}="wifi-pass-1234"\n'
            f'  {KEY_ADMIN_PASSWORD}="admin-pass-5678"  \n'
        )
        self.assertEqual(parse_secrets(text), valid_values(**{KEY_SSID: "Setup Net"}))

    def test_keeps_spaces_inside_quotes(self):
        text = render_secrets(" lead", "x", "y")
        self.assertEqual(parse_secrets(text)[KEY_SSID], " lead")

    def test_rejects_unknown_key(self):
        text = render_secrets("a", "b", "c") + 'CONFIG_REPEATER_TYPO="x"\n'
        with self.assertRaisesRegex(SecretsError, "unknown key CONFIG_REPEATER_TYPO"):
            parse_secrets(text)

    def test_rejects_duplicate_key(self):
        text = render_secrets("a", "b", "c") + f'{KEY_SSID}="again"\n'
        with self.assertRaisesRegex(SecretsError, "set twice"):
            parse_secrets(text)

    def test_rejects_missing_key(self):
        with self.assertRaisesRegex(SecretsError, "missing keys"):
            parse_secrets(f'{KEY_SSID}="a"\n')

    def test_rejects_unquoted_value(self):
        with self.assertRaisesRegex(SecretsError, "line 1"):
            parse_secrets(f"{KEY_SSID}=unquoted\n")


class ValidateSecretsTest(unittest.TestCase):
    def assertValid(self, values):
        self.assertEqual(validate_secrets(values), [])

    def assertInvalid(self, values, fragment):
        errors = validate_secrets(values)
        self.assertTrue(any(fragment in e for e in errors), f"{fragment!r} not in {errors}")

    def test_valid_values_pass(self):
        self.assertValid(valid_values())

    def test_password_length_bounds(self):
        self.assertValid(valid_values(**{KEY_AP_PASSWORD: "a" * 8}))
        self.assertValid(valid_values(**{KEY_AP_PASSWORD: "a" * 63}))
        self.assertInvalid(valid_values(**{KEY_AP_PASSWORD: "a" * 7}), "8-63 characters")
        self.assertInvalid(valid_values(**{KEY_AP_PASSWORD: "a" * 64}), "8-63 characters")

    def test_placeholder_rejected(self):
        self.assertInvalid(valid_values(**{KEY_AP_PASSWORD: "REPLACE_ME_8_to_63_chars"}), "placeholder")
        self.assertInvalid(valid_values(**{KEY_SSID: "REPLACE_ME"}), "placeholder")

    def test_example_file_is_rejected(self):
        values = parse_secrets((REPO_ROOT / "config" / "secrets.example").read_text(encoding="utf-8"))
        self.assertNotEqual(validate_secrets(values), [])

    def test_non_ascii_and_quotes_rejected(self):
        self.assertInvalid(valid_values(**{KEY_AP_PASSWORD: "pässwört123"}), "printable ASCII")
        self.assertInvalid(valid_values(**{KEY_AP_PASSWORD: 'abc"defgh'}), "double quote")
        self.assertInvalid(valid_values(**{KEY_AP_PASSWORD: "abc\\defgh"}), "backslash")

    def test_leading_or_trailing_space_rejected(self):
        self.assertInvalid(valid_values(**{KEY_AP_PASSWORD: " abcdefgh"}), "start or end")
        self.assertInvalid(valid_values(**{KEY_SSID: "net "}), "start or end")

    def test_symbols_allowed(self):
        # Verified to pass through ESP-IDF v5.5.4 kconfgen literally (no $ expansion).
        self.assertValid(valid_values(**{KEY_AP_PASSWORD: "a$b#c%d!e&f'g(h)*+,-./:;<=>?@[]^_`{|}~"}))
        self.assertValid(valid_values(**{KEY_AP_PASSWORD: "what?? no-trigraph?a"}))

    def test_trigraphs_rejected(self):
        for trigraph in ("??=", "??(", "??/", "??)", "??'", "??<", "??!", "??>", "??-"):
            with self.subTest(trigraph=trigraph):
                self.assertInvalid(valid_values(**{KEY_AP_PASSWORD: f"pass{trigraph}word"}), "trigraph")
        self.assertInvalid(valid_values(**{KEY_SSID: "Net??!"}), "trigraph")

    def test_ssid_limit_counts_utf8_bytes(self):
        self.assertValid(valid_values(**{KEY_SSID: "x" * 31}))
        self.assertInvalid(valid_values(**{KEY_SSID: "x" * 32}), "1-31 bytes")
        # 16 two-byte characters = 32 bytes
        self.assertInvalid(valid_values(**{KEY_SSID: "é" * 16}), "1-31 bytes")
        self.assertInvalid(valid_values(**{KEY_SSID: ""}), "1-31 bytes")

    def test_ssid_control_characters_rejected(self):
        self.assertInvalid(valid_values(**{KEY_SSID: "bad\tname"}), "control characters")

    def test_admin_must_differ_from_ap_password(self):
        self.assertInvalid(
            valid_values(**{KEY_ADMIN_PASSWORD: "wifi-pass-1234"}), "must differ"
        )

    def test_admin_password_must_fit_login_field(self):
        # 42 symbols encode to 126 bytes (fits); 43 encode to 129 (does not).
        self.assertValid(valid_values(**{KEY_ADMIN_PASSWORD: "!" * 42}))
        self.assertInvalid(valid_values(**{KEY_ADMIN_PASSWORD: "!" * 43}), "URL-encoded")


class FormEncodingTest(unittest.TestCase):
    def test_lengths(self):
        self.assertEqual(form_encoded_length("abcXYZ019"), 9)
        self.assertEqual(form_encoded_length("*-._"), 4)
        self.assertEqual(form_encoded_length(" "), 1)    # '+'
        self.assertEqual(form_encoded_length("~"), 3)    # browsers encode '~'
        self.assertEqual(form_encoded_length("é"), 6)    # two UTF-8 bytes


class GeneratePasswordTest(unittest.TestCase):
    def test_format_and_validity(self):
        ap, admin = generate_password(4), generate_password(5)
        self.assertRegex(ap, r"^[a-z0-9]{4}(-[a-z0-9]{4}){3}$")
        self.assertRegex(admin, r"^[a-z0-9]{4}(-[a-z0-9]{4}){4}$")
        self.assertEqual(validate_secrets(valid_values(**{KEY_AP_PASSWORD: ap, KEY_ADMIN_PASSWORD: admin})), [])

    def test_passwords_are_random(self):
        self.assertEqual(len({generate_password(4) for _ in range(50)}), 50)

    def test_render_round_trip(self):
        text = render_secrets("Setup", "wifi-pass-1234", "admin-pass-5678")
        self.assertEqual(parse_secrets(text), valid_values(**{KEY_SSID: "Setup"}))


class ArchiveSafetyTest(unittest.TestCase):
    def test_safe_member_names(self):
        self.assertTrue(is_safe_member("main/esp32_nat_router.c"))
        self.assertFalse(is_safe_member("/etc/passwd"))
        self.assertFalse(is_safe_member("../outside.c"))
        self.assertFalse(is_safe_member("main/../../outside.c"))


class PartitionTest(unittest.TestCase):
    CSV = (
        "# Name,   Type, SubType, Offset,  Size, Flags\n"
        "nvs,      data, nvs,     0x9000,  24K,\n"
        "ota_0,    app,  ota_0,   0x20000, 1536K,\n"
        "storage,  data, fat,     ,        0x50000,\n"
    )

    def test_sizes(self):
        self.assertEqual(parse_partition_size(self.CSV, "ota_0"), 1536 * 1024)
        self.assertEqual(parse_partition_size(self.CSV, "nvs"), 24 * 1024)
        self.assertEqual(parse_partition_size(self.CSV, "storage"), 0x50000)
        self.assertIsNone(parse_partition_size(self.CSV, "missing"))

    def test_upstream_partition_table(self):
        csv = REPO_ROOT / "build" / "src" / "partitions_example.csv"
        if not csv.is_file():
            self.skipTest("run `python tools/repeater.py prepare` first")
        self.assertEqual(parse_partition_size(csv.read_text(encoding="utf-8"), "ota_0"), 1536 * 1024)


class RemoveTreeGuardTest(unittest.TestCase):
    def test_refuses_paths_outside_expected_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "build"
            child = parent / "src"
            child.mkdir(parents=True)
            other = Path(tmp) / "elsewhere"
            other.mkdir()
            with self.assertRaises(ToolError):
                remove_tree(other, parent)
            self.assertTrue(other.exists())
            remove_tree(child, parent)
            self.assertFalse(child.exists())

    def test_refuses_filesystem_root(self):
        anchor = Path(Path.cwd().anchor)
        with self.assertRaises(ToolError):
            remove_tree(anchor, anchor)


def upstream_available() -> bool:
    import subprocess
    probe = subprocess.run(
        ["git", "-C", str(repeater.UPSTREAM_DIR), "cat-file", "-e", f"{repeater.UPSTREAM_COMMIT}^{{commit}}"],
        capture_output=True,
    )
    return probe.returncode == 0


@unittest.skipUnless(upstream_available(), "upstream submodule not checked out")
class PrepareIntegrationTest(unittest.TestCase):
    """Exports the pinned upstream and applies the real patches (needs git, not ESP-IDF)."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._old_env = repeater.os.environ.get("REPEATER_BUILD_DIR")
        repeater.os.environ["REPEATER_BUILD_DIR"] = str(Path(cls._tmp.name) / "build")
        cls.src = repeater.prepare(force=True)

    @classmethod
    def tearDownClass(cls):
        if cls._old_env is None:
            repeater.os.environ.pop("REPEATER_BUILD_DIR", None)
        else:
            repeater.os.environ["REPEATER_BUILD_DIR"] = cls._old_env
        cls._tmp.cleanup()

    def test_patches_applied(self):
        main_c = (self.src / "main" / "esp32_nat_router.c").read_text(encoding="utf-8")
        self.assertIn("apply_first_boot_security_defaults", main_c)
        self.assertIn("CONFIG_REPEATER_SETUP_AP_PASSWORD", main_c)
        http = (self.src / "components" / "http_server" / "http_server.c").read_text(encoding="utf-8")
        self.assertNotIn('"VPN query => %s"', http)
        self.assertTrue((self.src / "components" / "cmd_router" / "input_validation.h").is_file())

    def test_staged_files_use_lf(self):
        for relative in ("main/esp32_nat_router.c", "components/cmd_router/cmd_router.c",
                         "components/cmd_router/input_validation.h", "main/Kconfig.projbuild"):
            with self.subTest(file=relative):
                self.assertNotIn(b"\r\n", (self.src / relative).read_bytes())

    def test_second_prepare_is_a_no_op(self):
        marker = self.src / "untouched.marker"
        marker.write_text("x", encoding="utf-8")
        repeater.prepare()
        self.assertTrue(marker.exists(), "prepare() re-exported although nothing changed")

    def test_sdkconfig_regenerated_when_secrets_change(self):
        secrets_file = Path(self._tmp.name) / "secrets.test"
        secrets_file.write_text(render_secrets("Setup", "wifi-pass-1234", "admin-pass-5678"), encoding="utf-8")
        original = repeater.SECRETS_FILE
        repeater.SECRETS_FILE = secrets_file
        try:
            repeater.refresh_sdkconfig_if_inputs_changed("5.5.4")
            sdkconfig = repeater.sdkconfig_path()
            sdkconfig.write_text("stale\n", encoding="utf-8")
            repeater.refresh_sdkconfig_if_inputs_changed("5.5.4")
            self.assertTrue(sdkconfig.exists(), "unchanged inputs must keep the sdkconfig")
            secrets_file.write_text(render_secrets("Setup", "wifi-pass-9999", "admin-pass-5678"), encoding="utf-8")
            repeater.refresh_sdkconfig_if_inputs_changed("5.5.4")
            self.assertFalse(sdkconfig.exists(), "changed secrets must force regeneration")
        finally:
            repeater.SECRETS_FILE = original


class CliTest(unittest.TestCase):
    def test_check_secrets_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good"
            good.write_text(render_secrets("Setup", "wifi-pass-1234", "admin-pass-5678"), encoding="utf-8")
            bad = Path(tmp) / "bad"
            bad.write_text(render_secrets("Setup", "short", "admin-pass-5678"), encoding="utf-8")
            self.assertEqual(repeater.main(["check-secrets", "--file", str(good)]), 0)
            self.assertEqual(repeater.main(["check-secrets", "--file", str(bad)]), 2)


if __name__ == "__main__":
    unittest.main()

/* Host unit tests for input_validation.h (added by patch 0003).
 *
 * The header is header-only C99, so it is compiled here with the host
 * compiler, without ESP-IDF. Run via:
 *
 *     python tools/repeater.py prepare
 *     python tests/host/run_host_tests.py
 *
 * Each CHECK prints the failing expression; the exit code is the number of
 * failures, so CI fails on any regression.
 *
 * SPDX-License-Identifier: MIT
 */
#include <stdio.h>
#include <string.h>

#include "input_validation.h"

static int failures = 0;
static int checks = 0;

#define CHECK(expr)                                                   \
    do {                                                              \
        checks++;                                                     \
        if (!(expr)) {                                                \
            failures++;                                               \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #expr);    \
        }                                                             \
    } while (0)

static void repeat(char *buf, char c, size_t n)
{
    memset(buf, c, n);
    buf[n] = '\0';
}

static void test_ssid(void)
{
    char buf[64];
    CHECK(!ssid_is_valid(""));
    CHECK(ssid_is_valid("a"));
    CHECK(ssid_is_valid("My Home WiFi"));
    repeat(buf, 'x', 31);
    CHECK(ssid_is_valid(buf));
    repeat(buf, 'x', 32);  /* would be truncated by strlcpy into ssid[32] */
    CHECK(!ssid_is_valid(buf));
}

static void test_sta_ssid(void)
{
    char buf[64];
    CHECK(sta_ssid_is_valid(""));   /* no uplink: setup mode */
    CHECK(sta_ssid_is_valid("Home"));
    repeat(buf, 'x', 31);
    CHECK(sta_ssid_is_valid(buf));
    repeat(buf, 'x', 32);
    CHECK(!sta_ssid_is_valid(buf));
}

static void test_ap_passphrase(void)
{
    char buf[80];
    CHECK(ap_passphrase_is_valid(""));            /* explicit open AP */
    CHECK(!ap_passphrase_is_valid("1"));
    CHECK(!ap_passphrase_is_valid("1234567"));    /* upstream made this an open AP */
    CHECK(ap_passphrase_is_valid("12345678"));
    CHECK(ap_passphrase_is_valid("with spaces and $ymbols!"));
    repeat(buf, 'p', 63);
    CHECK(ap_passphrase_is_valid(buf));
    repeat(buf, 'p', 64);
    CHECK(!ap_passphrase_is_valid(buf));
    CHECK(!ap_passphrase_is_valid("tab\there12"));
    CHECK(!ap_passphrase_is_valid("caf\xc3\xa9-latte"));  /* UTF-8, not printable ASCII */
    CHECK(!ap_passphrase_is_valid("del\x7f" "chars1"));
}

static void test_parse_ipv4_strict(void)
{
    uint8_t o[4];
    CHECK(parse_ipv4_strict("192.168.4.1", o) && o[0] == 192 && o[1] == 168 && o[2] == 4 && o[3] == 1);
    CHECK(parse_ipv4_strict("0.0.0.0", o));
    CHECK(parse_ipv4_strict("255.255.255.255", o));
    CHECK(!parse_ipv4_strict("", o));
    CHECK(!parse_ipv4_strict("garbage", o));
    CHECK(!parse_ipv4_strict("10", o));            /* inet_aton would accept this */
    CHECK(!parse_ipv4_strict("10.1", o));
    CHECK(!parse_ipv4_strict("1.2.3", o));
    CHECK(!parse_ipv4_strict("1.2.3.4.5", o));
    CHECK(!parse_ipv4_strict("256.1.1.1", o));
    CHECK(!parse_ipv4_strict("1.2.3.0004", o));
    CHECK(!parse_ipv4_strict(" 1.2.3.4", o));
    CHECK(!parse_ipv4_strict("1.2.3.4 ", o));
    CHECK(!parse_ipv4_strict("1..3.4", o));
    CHECK(!parse_ipv4_strict("-1.2.3.4", o));
    CHECK(!parse_ipv4_strict("1.2.3.4/24", o));
}

static void test_ap_ip(void)
{
    CHECK(ap_ip_is_valid("192.168.4.1"));
    CHECK(ap_ip_is_valid("10.0.0.1"));
    CHECK(ap_ip_is_valid("172.16.5.254"));
    CHECK(!ap_ip_is_valid("garbage"));             /* stored as 0.0.0.0 upstream */
    CHECK(!ap_ip_is_valid("0.0.0.0"));
    CHECK(!ap_ip_is_valid("0.1.2.3"));
    CHECK(!ap_ip_is_valid("127.0.0.1"));
    CHECK(!ap_ip_is_valid("169.254.1.1"));
    CHECK(!ap_ip_is_valid("224.0.0.1"));
    CHECK(!ap_ip_is_valid("255.255.255.255"));
    CHECK(!ap_ip_is_valid("192.168.4.0"));         /* /24 network address */
    CHECK(!ap_ip_is_valid("192.168.4.255"));       /* /24 broadcast address */
}

int main(void)
{
    test_ssid();
    test_sta_ssid();
    test_ap_passphrase();
    test_parse_ipv4_strict();
    test_ap_ip();
    printf("%d checks, %d failures\n", checks, failures);
    return failures;
}

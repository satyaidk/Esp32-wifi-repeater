# ADR 0002: Pin upstream as a submodule and apply a patch queue at build time

- Status: Accepted
- Date: 2026-10-23

## Context

The firmware should reuse upstream's DHCP, NAT, web UI, CLI and persistence
rather than duplicate them, yet a few changes are required (secure defaults,
log redaction, input validation, a build fix). Constraints found while
inspecting upstream:

- Upstream has no repository-level license (GitHub reports none). Individual
  files carry MIT, Apache-2.0, CC0 or BSD-3-Clause headers and several carry
  none. Copying the tree into this repository would mean redistributing files
  whose terms are unclear.
- Components include `${CMAKE_SOURCE_DIR}/include`, so the upstream tree must
  be the CMake project root; it cannot simply be added as extra components.
- Git for Windows checks files out with CRLF (`core.autocrlf=true`), and LF
  patches do not apply to such a checkout.

## Decision

- `upstream/esp32_nat_router` is a git submodule pinned to `119e0a3`. It is
  never edited.
- `patches/*.patch` (`git format-patch` output, LF, marked `-text` in
  `.gitattributes`) hold every change, each with a commit message explaining
  the defect.
- `tools/repeater.py prepare` exports the pinned commit with `git archive`
  (LF regardless of local settings) into `build/src`, initialises a private
  git repository there with EOL conversion disabled, and applies the patches
  with `git apply --check` first. The staging tree is recreated whenever the
  commit, a patch or the component lock changes.

## Consequences

- This repository contains only original work (tooling, configuration, docs,
  patches) under MIT. Upstream code is fetched from upstream.
- Updating upstream is explicit: move the submodule, update
  `UPSTREAM_COMMIT`, refresh patches until `prepare` succeeds (see
  CONTRIBUTING.md).
- Builds are identical on Windows, Linux and CI.
- Editing files in `build/src` by hand is pointless: they are regenerated.
  Changes go into a patch.

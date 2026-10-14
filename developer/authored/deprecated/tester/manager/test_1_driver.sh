#!/usr/bin/env bash
# test_1_driver.sh — smoke test: Unix dry mode + make

set -x

# 1) Put Unix handling into dry-run mode.
#    In this mode we expect *no real* user/group changes.
CLI.py option Unix dry

# 2) Make a first-level subu
CLI.py make Thomas S0

# 3) Make a second-level subu under the first
CLI.py make Thomas S0 S1

# 4) Return Unix handling to run mode (for future tests)
CLI.py option Unix run

set +x

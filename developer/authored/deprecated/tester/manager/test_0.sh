#!/usr/bin/env bash

{ . test_0_driver.sh 2> >(tee /dev/stderr >&3); } 3>test_0_out.sh 1>&3
set -x
diff -qr test_0_out.sh test_0_expected.sh
set +x

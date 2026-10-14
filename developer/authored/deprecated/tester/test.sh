#!/bin/env bash

set -x
./CLI                 # -> USAGE (exit 0)
./CLI usage           # -> USAGE
./CLI -h              # -> HELP
./CLI --help          # -> HELP
./CLI help            # -> HELP
./CLI help WG         # -> WG topic help (or full HELP if topic unknown)
./CLI example         # -> EXAMPLE
./CLI version         # -> 0.1.4
./CLI -V              # -> 0.1.4


set -x
./subu.py                 # -> USAGE (exit 0)
./subu.py usage           # -> USAGE
./subu.py -h              # -> HELP
./subu.py --help          # -> HELP
./subu.py help            # -> HELP
./subu.py help WG         # -> WG topic help (or full HELP if topic unknown)
./subu.py example         # -> EXAMPLE
./subu.py version         # -> 0.1.4
./subu.py -V              # -> 0.1.4
set +x

set -x
CLI.py                 # -> USAGE (exit 0)
CLI.py usage           # -> USAGE
CLI.py -h              # -> HELP
CLI.py --help          # -> HELP
CLI.py help            # -> HELP
CLI.py help WG         # -> WG topic help (or full HELP if topic unknown)
CLI.py example         # -> EXAMPLE
CLI.py version         # -> 0.1.4
CLI.py -V              # -> 0.1.4
set +x

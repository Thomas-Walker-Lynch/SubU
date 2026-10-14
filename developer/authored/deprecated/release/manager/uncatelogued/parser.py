verbs = [
    "usage",
    "help",
    "example",
    "version",
    "init",
    "make",
    "make",
    "info",
    "information",
    "WG",
    "attach",
    "detach",
    "network",
    "lo",
    "option",
    "exec",
]

p_make = subparsers.add_parser(
    "make",
    help="Create a Subu with hierarchical name + Unix user/groups + netns",
)
p_make.add_argument(
    "path",
    nargs="+",
    help="Full Subu path, e.g. 'Thomas US' or 'Thomas new-subu Rabbit'",
)

elif args.verb == "make":
    subu_id = core.make_subu(args.path)
    print(subu_id)

++ ./subu.py
usage: subu [-V] <verb> [<args>]

Quick verbs:
  usage                  Show this usage summary
  help [topic]           Detailed help; same as -h / --help
  example                End-to-end example session
  version                Print version

Main verbs:
  init                   Initialize a new subu database (refuses if it exists)
  create                 Create a minimal subu record (defaults only)
  info | information     Show details for a subu
  WG                     WireGuard object operations
  attach                 Attach a WG object to a subu (netns + cgroup/eBPF)
  detach                 Detach WG from a subu
  network                Bring all attached ifaces up/down inside the subu netns
  lo                     Bring loopback up/down inside the subu netns
  option                 Persisted options (list/set/get for future policy)
  exec                   Run a command inside the subu netns

Tip: `subu help` (or `subu --help`) shows detailed help; `subu help WG` shows topic help.
++ ./subu.py usage
usage: subu [-V] <verb> [<args>]

Quick verbs:
  usage                  Show this usage summary
  help [topic]           Detailed help; same as -h / --help
  example                End-to-end example session
  version                Print version

Main verbs:
  init                   Initialize a new subu database (refuses if it exists)
  create                 Create a minimal subu record (defaults only)
  info | information     Show details for a subu
  WG                     WireGuard object operations
  attach                 Attach a WG object to a subu (netns + cgroup/eBPF)
  detach                 Detach WG from a subu
  network                Bring all attached ifaces up/down inside the subu netns
  lo                     Bring loopback up/down inside the subu netns
  option                 Persisted options (list/set/get for future policy)
  exec                   Run a command inside the subu netns

Tip: `subu help` (or `subu --help`) shows detailed help; `subu help WG` shows topic help.
++ ./subu.py -h
subu — manage subu containers, namespaces, and WG attachments

2.1 Core

  subu init <TOKEN>
      Create ./subu.db (tables: subu, wg, links, options, state).
      Requires a 6-char token (e.g., dzkq7b). Refuses if DB already exists.

  subu create <masu> <subu>
      Make a default subu with netns ns-<Subu_ID> containing lo only (down).
      Returns subu_N.

  subu list
      Columns: Subu_ID, Owner, Name, NetNS, WG_Attached?, Up/Down, Steer?

  subu info <Subu_ID>    | subu information <Subu_ID>
      Full record + attached WG(s) + options + iface states.

2.2 Loopback

  subu lo up <Subu_ID>   | subu lo down <Subu_ID>
      Toggle loopback inside the subu’s netns.

2.3 WireGuard objects (independent)

  subu WG global <BaseCIDR>
      e.g., 192.168.112.0/24; allocator hands out /32 peers sequentially.
      Shows current base and next free on success.

  subu WG create <host:port>
      Creates WG object; allocates next /32 local IP; AllowedIPs=0.0.0.0/0.
      Returns WG_M.

  subu WG server_provided_public_key <WG_ID> <Base64Key>
      Stores server’s pubkey.

  subu WG info <WG_ID>   | subu WG information <WG_ID>
      Endpoint, allocated IP, pubkey set?, link state (admin/oper).

2.4 Link WG ↔ subu, bring up/down

  subu attach WG <Subu_ID> <WG_ID>
      Creates/configures WG device inside ns-<Subu_ID>:
        - device name: subu_<M> (M from WG_ID)
        - set local /32, MTU 1420, accept_local=1
        - (no default route is added — steering uses eBPF)
        - v1: enforce one WG per Subu; error if another attached

  subu detach WG <Subu_ID>
      Remove WG device/config from the subu’s netns; keep WG object.

  subu WG up <WG_ID>     | subu WG down <WG_ID>
      Toggle interface admin state in the subu’s netns (must be attached).

  subu network up <Subu_ID> | subu network down <Subu_ID>
      Only toggles admin state for all attached ifaces. On “up”, loopback
      is brought up first automatically. No route manipulation.

2.5 Execution & (future) steering

  subu exec <Subu_ID> -- <cmd> …
      Run a process inside the subu’s netns.

  subu steer enable <Subu_ID> | subu steer disable <Subu_ID>
      (Future) Attach/detach eBPF cgroup programs to force SO_BINDTOIFINDEX=subu_<M>
      for TCP/UDP. Default: disabled.

2.6 Options (persist only, for future policy)

  subu option list <Subu_ID>
  subu option get  <Subu_ID> [name]
  subu option set  <Subu_ID> <name> <value>

2.7 Meta

  subu usage
      Short usage summary (also printed when no args are given).

  subu help [topic]
      This help (or per-topic help such as `subu help WG`).

  subu example
      A concrete end-to-end scenario.

  subu version
      Print version (same as -V / --version).
++ ./subu.py --help
subu — manage subu containers, namespaces, and WG attachments

2.1 Core

  subu init <TOKEN>
      Create ./subu.db (tables: subu, wg, links, options, state).
      Requires a 6-char token (e.g., dzkq7b). Refuses if DB already exists.

  subu create <masu> <subu>
      Make a default subu with netns ns-<Subu_ID> containing lo only (down).
      Returns subu_N.

  subu list
      Columns: Subu_ID, Owner, Name, NetNS, WG_Attached?, Up/Down, Steer?

  subu info <Subu_ID>    | subu information <Subu_ID>
      Full record + attached WG(s) + options + iface states.

2.2 Loopback

  subu lo up <Subu_ID>   | subu lo down <Subu_ID>
      Toggle loopback inside the subu’s netns.

2.3 WireGuard objects (independent)

  subu WG global <BaseCIDR>
      e.g., 192.168.112.0/24; allocator hands out /32 peers sequentially.
      Shows current base and next free on success.

  subu WG create <host:port>
      Creates WG object; allocates next /32 local IP; AllowedIPs=0.0.0.0/0.
      Returns WG_M.

  subu WG server_provided_public_key <WG_ID> <Base64Key>
      Stores server’s pubkey.

  subu WG info <WG_ID>   | subu WG information <WG_ID>
      Endpoint, allocated IP, pubkey set?, link state (admin/oper).

2.4 Link WG ↔ subu, bring up/down

  subu attach WG <Subu_ID> <WG_ID>
      Creates/configures WG device inside ns-<Subu_ID>:
        - device name: subu_<M> (M from WG_ID)
        - set local /32, MTU 1420, accept_local=1
        - (no default route is added — steering uses eBPF)
        - v1: enforce one WG per Subu; error if another attached

  subu detach WG <Subu_ID>
      Remove WG device/config from the subu’s netns; keep WG object.

  subu WG up <WG_ID>     | subu WG down <WG_ID>
      Toggle interface admin state in the subu’s netns (must be attached).

  subu network up <Subu_ID> | subu network down <Subu_ID>
      Only toggles admin state for all attached ifaces. On “up”, loopback
      is brought up first automatically. No route manipulation.

2.5 Execution & (future) steering

  subu exec <Subu_ID> -- <cmd> …
      Run a process inside the subu’s netns.

  subu steer enable <Subu_ID> | subu steer disable <Subu_ID>
      (Future) Attach/detach eBPF cgroup programs to force SO_BINDTOIFINDEX=subu_<M>
      for TCP/UDP. Default: disabled.

2.6 Options (persist only, for future policy)

  subu option list <Subu_ID>
  subu option get  <Subu_ID> [name]
  subu option set  <Subu_ID> <name> <value>

2.7 Meta

  subu usage
      Short usage summary (also printed when no args are given).

  subu help [topic]
      This help (or per-topic help such as `subu help WG`).

  subu example
      A concrete end-to-end scenario.

  subu version
      Print version (same as -V / --version).
++ ./subu.py help
subu — manage subu containers, namespaces, and WG attachments

2.1 Core

  subu init <TOKEN>
      Create ./subu.db (tables: subu, wg, links, options, state).
      Requires a 6-char token (e.g., dzkq7b). Refuses if DB already exists.

  subu create <masu> <subu>
      Make a default subu with netns ns-<Subu_ID> containing lo only (down).
      Returns subu_N.

  subu list
      Columns: Subu_ID, Owner, Name, NetNS, WG_Attached?, Up/Down, Steer?

  subu info <Subu_ID>    | subu information <Subu_ID>
      Full record + attached WG(s) + options + iface states.

2.2 Loopback

  subu lo up <Subu_ID>   | subu lo down <Subu_ID>
      Toggle loopback inside the subu’s netns.

2.3 WireGuard objects (independent)

  subu WG global <BaseCIDR>
      e.g., 192.168.112.0/24; allocator hands out /32 peers sequentially.
      Shows current base and next free on success.

  subu WG create <host:port>
      Creates WG object; allocates next /32 local IP; AllowedIPs=0.0.0.0/0.
      Returns WG_M.

  subu WG server_provided_public_key <WG_ID> <Base64Key>
      Stores server’s pubkey.

  subu WG info <WG_ID>   | subu WG information <WG_ID>
      Endpoint, allocated IP, pubkey set?, link state (admin/oper).

2.4 Link WG ↔ subu, bring up/down

  subu attach WG <Subu_ID> <WG_ID>
      Creates/configures WG device inside ns-<Subu_ID>:
        - device name: subu_<M> (M from WG_ID)
        - set local /32, MTU 1420, accept_local=1
        - (no default route is added — steering uses eBPF)
        - v1: enforce one WG per Subu; error if another attached

  subu detach WG <Subu_ID>
      Remove WG device/config from the subu’s netns; keep WG object.

  subu WG up <WG_ID>     | subu WG down <WG_ID>
      Toggle interface admin state in the subu’s netns (must be attached).

  subu network up <Subu_ID> | subu network down <Subu_ID>
      Only toggles admin state for all attached ifaces. On “up”, loopback
      is brought up first automatically. No route manipulation.

2.5 Execution & (future) steering

  subu exec <Subu_ID> -- <cmd> …
      Run a process inside the subu’s netns.

  subu steer enable <Subu_ID> | subu steer disable <Subu_ID>
      (Future) Attach/detach eBPF cgroup programs to force SO_BINDTOIFINDEX=subu_<M>
      for TCP/UDP. Default: disabled.

2.6 Options (persist only, for future policy)

  subu option list <Subu_ID>
  subu option get  <Subu_ID> [name]
  subu option set  <Subu_ID> <name> <value>

2.7 Meta

  subu usage
      Short usage summary (also printed when no args are given).

  subu help [topic]
      This help (or per-topic help such as `subu help WG`).

  subu example
      A concrete end-to-end scenario.

  subu version
      Print version (same as -V / --version).
++ ./subu.py help WG
usage: subu WG [-h]

options:
  -h, --help  show this help message and exit
++ ./subu.py example
# 0) Safe init (refuses if ./subu.db exists)
subu init dzkq7b
# -> created ./subu.db

# 1) Create Subu
subu create Thomas US
# -> Subu_ID: subu_7
# -> netns: ns-subu_7 with lo (down)

# 2) Define WG pool (once per host)
subu WG global 192.168.112.0/24
# -> base set; next free: 192.168.112.2/32

# 3) Create WG object with endpoint
subu WG create ReasoningTechnology.com:51820
# -> WG_ID: WG_0
# -> local IP: 192.168.112.2/32
# -> AllowedIPs: 0.0.0.0/0

# 4) Add server public key
subu WG server_provided_public_key WG_0 ABCDEFG...xyz=
# -> saved

# 5) Attach WG to Subu (device created/configured in ns)
subu attach WG subu_7 WG_0
# -> device ns-subu_7/subu_0 configured (no default route)

# 6) Bring network up (lo first, then attached ifaces)
subu network up subu_7
# -> lo up; subu_0 admin up

# 7) Start the WG engine inside the netns
subu WG up WG_0
# -> up, handshakes should start

# 8) Test from inside the subu
subu exec subu_7 -- curl -4v https://ifconfig.me
++ ./subu.py version
0.1.3
++ ./subu.py -V
0.1.3
++ set +x

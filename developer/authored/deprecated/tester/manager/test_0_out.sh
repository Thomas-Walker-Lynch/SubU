++ CLI.py
Subu manager (v0.3.3)

1) Init
  CLI.py init <TOKEN>
    Makes ./subu.db. Refuses to run if db exists.

2) Subu
  CLI.py make <masu> <subu> [_<subu>]*
  CLI.py list
  CLI.py info <Subu_ID>

3) Loopback
  CLI.py lo up|down <Subu_ID>

4) WireGuard objects (independent of subu)
  CLI.py WG global <BaseCIDR>                 # for example, 192.168.112.0/24
  CLI.py WG make <host:port>                # allocates next /32
  CLI.py WG server_provided_public_key <WG_ID> <Base64Key>
  CLI.py WG info <WG_ID>
  CLI.py WG up <WG_ID> / CLI.py WG down <WG_ID> # administrative toggle after attached

5) Attach or detach and eBPF steering
  CLI.py attach WG <Subu_ID> <WG_ID>
    - Makes WireGuard device as subu_<M> inside ns-subu_<N>, assigns /32, MTU 1420
    - Installs per-subu cgroup and loads eBPF scaffold (user identifier check, metadata map)
    - Keeps device administrative-down until `CLI.py network up`
  CLI.py detach WG <Subu_ID>
    - Deletes device, removes cgroup and eBPF program

6) Network aggregate
  CLI.py network up|down <Subu_ID>
    - Ensures loopback is up on 'up', toggles attached WireGuard interfaces

7) Options
  CLI.py option set|get|list ...

8) Exec
  CLI.py exec <Subu_ID> -- <cmd> ...
++ CLI.py usage
CLI.py — Subu manager (v0.3.3)

Usage:
  CLI.py                   # usage
  CLI.py help              # detailed help
  CLI.py example           # example workflow
  CLI.py version           # print version

  CLI.py init <TOKEN>
  CLI.py make <masu> <subu> [_<subu>]*
  CLI.py list
  CLI.py info <Subu_ID> | CLI.py information <Subu_ID>

  CLI.py lo up|down <Subu_ID>

  CLI.py WG global <BaseCIDR>
  CLI.py WG make <host:port>
  CLI.py WG server_provided_public_key <WG_ID> <Base64Key>
  CLI.py WG info|information <WG_ID>
  CLI.py WG up <WG_ID>
  CLI.py WG down <WG_ID>

  CLI.py attach WG <Subu_ID> <WG_ID>
  CLI.py detach WG <Subu_ID>

  CLI.py network up|down <Subu_ID>

  CLI.py option set <Subu_ID> <subu> <value>
  CLI.py option get <Subu_ID> <subu>
  CLI.py option list <Subu_ID>

  CLI.py exec <Subu_ID> -- <cmd> ...
++ CLI.py -h
Subu manager (v0.3.3)

1) Init
  CLI.py init <TOKEN>
    Makes ./subu.db. Refuses to run if db exists.

2) Subu
  CLI.py make <masu> <subu> [_<subu>]*
  CLI.py list
  CLI.py info <Subu_ID>

3) Loopback
  CLI.py lo up|down <Subu_ID>

4) WireGuard objects (independent of subu)
  CLI.py WG global <BaseCIDR>                 # for example, 192.168.112.0/24
  CLI.py WG make <host:port>                # allocates next /32
  CLI.py WG server_provided_public_key <WG_ID> <Base64Key>
  CLI.py WG info <WG_ID>
  CLI.py WG up <WG_ID> / CLI.py WG down <WG_ID> # administrative toggle after attached

5) Attach or detach and eBPF steering
  CLI.py attach WG <Subu_ID> <WG_ID>
    - Makes WireGuard device as subu_<M> inside ns-subu_<N>, assigns /32, MTU 1420
    - Installs per-subu cgroup and loads eBPF scaffold (user identifier check, metadata map)
    - Keeps device administrative-down until `CLI.py network up`
  CLI.py detach WG <Subu_ID>
    - Deletes device, removes cgroup and eBPF program

6) Network aggregate
  CLI.py network up|down <Subu_ID>
    - Ensures loopback is up on 'up', toggles attached WireGuard interfaces

7) Options
  CLI.py option set|get|list ...

8) Exec
  CLI.py exec <Subu_ID> -- <cmd> ...
++ CLI.py --help
Subu manager (v0.3.3)

1) Init
  CLI.py init <TOKEN>
    Makes ./subu.db. Refuses to run if db exists.

2) Subu
  CLI.py make <masu> <subu> [_<subu>]*
  CLI.py list
  CLI.py info <Subu_ID>

3) Loopback
  CLI.py lo up|down <Subu_ID>

4) WireGuard objects (independent of subu)
  CLI.py WG global <BaseCIDR>                 # for example, 192.168.112.0/24
  CLI.py WG make <host:port>                # allocates next /32
  CLI.py WG server_provided_public_key <WG_ID> <Base64Key>
  CLI.py WG info <WG_ID>
  CLI.py WG up <WG_ID> / CLI.py WG down <WG_ID> # administrative toggle after attached

5) Attach or detach and eBPF steering
  CLI.py attach WG <Subu_ID> <WG_ID>
    - Makes WireGuard device as subu_<M> inside ns-subu_<N>, assigns /32, MTU 1420
    - Installs per-subu cgroup and loads eBPF scaffold (user identifier check, metadata map)
    - Keeps device administrative-down until `CLI.py network up`
  CLI.py detach WG <Subu_ID>
    - Deletes device, removes cgroup and eBPF program

6) Network aggregate
  CLI.py network up|down <Subu_ID>
    - Ensures loopback is up on 'up', toggles attached WireGuard interfaces

7) Options
  CLI.py option set|get|list ...

8) Exec
  CLI.py exec <Subu_ID> -- <cmd> ...
++ CLI.py help
Subu manager (v0.3.3)

1) Init
  CLI.py init <TOKEN>
    Makes ./subu.db. Refuses to run if db exists.

2) Subu
  CLI.py make <masu> <subu> [_<subu>]*
  CLI.py list
  CLI.py info <Subu_ID>

3) Loopback
  CLI.py lo up|down <Subu_ID>

4) WireGuard objects (independent of subu)
  CLI.py WG global <BaseCIDR>                 # for example, 192.168.112.0/24
  CLI.py WG make <host:port>                # allocates next /32
  CLI.py WG server_provided_public_key <WG_ID> <Base64Key>
  CLI.py WG info <WG_ID>
  CLI.py WG up <WG_ID> / CLI.py WG down <WG_ID> # administrative toggle after attached

5) Attach or detach and eBPF steering
  CLI.py attach WG <Subu_ID> <WG_ID>
    - Makes WireGuard device as subu_<M> inside ns-subu_<N>, assigns /32, MTU 1420
    - Installs per-subu cgroup and loads eBPF scaffold (user identifier check, metadata map)
    - Keeps device administrative-down until `CLI.py network up`
  CLI.py detach WG <Subu_ID>
    - Deletes device, removes cgroup and eBPF program

6) Network aggregate
  CLI.py network up|down <Subu_ID>
    - Ensures loopback is up on 'up', toggles attached WireGuard interfaces

7) Options
  CLI.py option set|get|list ...

8) Exec
  CLI.py exec <Subu_ID> -- <cmd> ...
++ CLI.py help WG
Subu manager (v0.3.3)

1) Init
  CLI.py init <TOKEN>
    Makes ./subu.db. Refuses to run if db exists.

2) Subu
  CLI.py make <masu> <subu> [_<subu>]*
  CLI.py list
  CLI.py info <Subu_ID>

3) Loopback
  CLI.py lo up|down <Subu_ID>

4) WireGuard objects (independent of subu)
  CLI.py WG global <BaseCIDR>                 # for example, 192.168.112.0/24
  CLI.py WG make <host:port>                # allocates next /32
  CLI.py WG server_provided_public_key <WG_ID> <Base64Key>
  CLI.py WG info <WG_ID>
  CLI.py WG up <WG_ID> / CLI.py WG down <WG_ID> # administrative toggle after attached

5) Attach or detach and eBPF steering
  CLI.py attach WG <Subu_ID> <WG_ID>
    - Makes WireGuard device as subu_<M> inside ns-subu_<N>, assigns /32, MTU 1420
    - Installs per-subu cgroup and loads eBPF scaffold (user identifier check, metadata map)
    - Keeps device administrative-down until `CLI.py network up`
  CLI.py detach WG <Subu_ID>
    - Deletes device, removes cgroup and eBPF program

6) Network aggregate
  CLI.py network up|down <Subu_ID>
    - Ensures loopback is up on 'up', toggles attached WireGuard interfaces

7) Options
  CLI.py option set|get|list ...

8) Exec
  CLI.py exec <Subu_ID> -- <cmd> ...
++ CLI.py example
# 0) Initialise the subu database (once per directory)
CLI.py init dzkq7b

# 1) Make Subu
CLI.py make Thomas US
# -> subu_1

# 2) WireGuard pool once
CLI.py WG global 192.168.112.0/24

# 3) Make WireGuard object with endpoint
CLI.py WG make ReasoningTechnology.com:51820
# -> WG_1

# 4) Server public key (placeholder)
CLI.py WG server_provided_public_key WG_1 ABCDEFG...xyz=

# 5) Attach device and install cgroup and eBPF steering
CLI.py attach WG subu_1 WG_1

# 6) Bring network up (loopback and WireGuard)
CLI.py network up subu_1

# 7) Test inside namespace
CLI.py exec subu_1 -- curl -4v https://ifconfig.me
++ CLI.py version
0.3.3++ CLI.py -V
0.3.3++ set +x

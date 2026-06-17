# Networking

External addresses are selected in this order:

1. RTPengine replica override.
2. Component-level override.
3. Explicit value from the referenced `NetworkProfile`.
4. The component LoadBalancer Service ingress.
5. An unresolved-address condition for externally exposed components.

For cluster-local `ClusterIP` components, KubeVoIP uses the managed Service DNS
name. A hostname used by RTPengine is resolved inside its Pod before startup
because SDP requires an IP address.

For LoadBalancer components without an explicit address, KubeVoIP first creates
the managed Service and reports `WaitingForLoadBalancer` while its ingress is
pending. Once MetalLB or the cloud provider assigns an address, reconciliation
continues and starts or rolls the component with that advertised address.

`SIPGateway.spec.internalAddress` controls the SIP route advertised to internal
registered endpoints. If omitted, KubeVoIP uses the SIP gateway Service ingress
when available, otherwise the managed Service DNS name. This lets trunk-facing
dialogs advertise a public address while LAN phones receive an internal
Record-Route target for in-dialog requests such as `ACK`, `BYE`, and re-INVITE.

Kamailio receives SIP, writes registrations to PostgreSQL, selects a route, and
asks an RTPengine replica to rewrite SDP. Direct trunk-to-phone media flows
through RTPengine without Asterisk. Calls to an `AsteriskPool` application flow
through RTPengine and one selected Asterisk worker.

IP-authenticated trunks trust only `SIPTrunk.spec.inbound.allowedSourceCidrs`.
Untrusted INVITEs receive a proxy-authentication challenge and must authenticate
as a `SIPUser`. Outbound `CallRoute` resources select a declared trunk with
`trunkRef`.

Outbound trunks can optionally use Secret-backed caller ID and SIP digest
credentials. KubeVoIP injects those values into Kamailio as environment
variables and keeps raw credential values out of rendered ConfigMaps, statuses,
Events, and logs.

Public forwarding must preserve port numbers. Forward UDP `5060` to the
Kamailio address and each RTPengine replica's assigned range to that replica's
address. Do not translate those ports.

`HostNetwork` avoids Kubernetes Service NAT for media but binds ports directly
on selected nodes. Scheduling, node public addresses, firewall rules, and port
conflicts are then cluster-operator responsibilities.

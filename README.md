# KubeVoIP

[![Test](https://github.com/danohn/kubevoip/actions/workflows/test.yaml/badge.svg)](https://github.com/danohn/kubevoip/actions/workflows/test.yaml)
[![Integration](https://github.com/danohn/kubevoip/actions/workflows/integration.yaml/badge.svg)](https://github.com/danohn/kubevoip/actions/workflows/integration.yaml)

KubeVoIP is a Kubernetes operator for SIP platforms. Version 0.2 introduces
experimental Kamailio gateways, RTPengine media relays, PostgreSQL-backed SIP
users, and interchangeable Asterisk application workers. The original
single-instance `Asterisk` API remains available under the new API group.

Project home: [https://kubevoip.com](https://kubevoip.com)

## Install

```bash
helm install kubevoip oci://ghcr.io/danohn/charts/kubevoip \
  --version 0.2.0 \
  --namespace telephony --create-namespace
```

KubeVoIP v0.2 installs only `kubevoip.com/v1alpha1` CRDs. Existing v0.1
`kubevoip.io` resources must be exported and recreated; see
[docs/migration-v0.2.md](docs/migration-v0.2.md).

Each Helm release watches and manages only its installation namespace. Its
ServiceAccount receives a namespaced Role, including Secret access only in that
namespace. Install a separate release for each telephony namespace:

```bash
helm install kubevoip-home oci://ghcr.io/danohn/charts/kubevoip \
  --version 0.2.0 --namespace telephony-home --create-namespace
helm install kubevoip-office oci://ghcr.io/danohn/charts/kubevoip \
  --version 0.2.0 --namespace telephony-office --create-namespace
```

CRDs remain cluster-scoped Kubernetes resources shared by all releases.

## APIs

- `Asterisk`: the v0.1 single-PBX model, moved unchanged to `kubevoip.com`.
- `NetworkProfile`: shared external addressing and local-network policy.
- `SIPUser`: a PostgreSQL-backed identity registered through Kamailio.
- `MediaRelay`: stable, horizontally scalable RTPengine replicas.
- `AsteriskPool`: private application workers, currently providing Echo.
- `SIPGateway`: Kamailio registration, media-relay, trunk, and route policy.

Platform resources are experimental in v0.2. References are namespaced and
must point to resources in the same namespace.

```bash
kubectl apply -f examples/namespace.yaml
kubectl apply -f examples/platform.yaml
kubectl -n asterisk-demo get networkprofile,mediarelay,asteriskpool
```

A PostgreSQL database and a standard connection Secret are required before
creating `SIPGateway` and `SIPUser` resources. KubeVoIP does not install or
require CNPG. The Secret keys are `host`, `port`, `dbname`, `user`, and
`password`.

## External Networking

Set `NetworkProfile.spec.externalAddress.value` to an IP address or hostname,
or set `source: Service` to discover addresses from managed LoadBalancer
Services. Component overrides and RTPengine replica overrides take precedence.

KubeVoIP rewrites SIP advertised addresses and RTPengine SDP addresses. Public
forwarding must preserve UDP port numbers: SIP `5060` and each assigned
RTPengine range must use identical public and private ports. Provider load
balancer behavior, firewall rules, DNS, router forwarding, and trunk-provider
configuration remain the user's responsibility.

`Service` and `HostNetwork` media modes are experimental. UDP SIP is the only
supported transport. TLS, WebRTC, and active-call failover are not included in
v0.2. A namespace and its dedicated operator release form the supported
isolation boundary.

IP-authenticated trunks must declare `allowedSourceCidrs`. Calls arriving from
those networks bypass subscriber authentication. Other INVITEs must
authenticate as a `SIPUser`. Routes can target a `sipUserRef`,
`asteriskPoolRef`, or declared `trunkRef`.

See [docs/networking.md](docs/networking.md) for precedence and packet-flow
details.

## Development

Requirements: Python 3.12+, `uv`, Helm 3, Docker, and Kubernetes.

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest
helm lint charts/kubevoip
helm template kubevoip charts/kubevoip
kubectl apply --dry-run=server -f config/crd/asterisk-crd.yaml
kubectl apply --dry-run=server -f config/crd/platform-crds.yaml
```

Run the controller against the current cluster:

```bash
kubectl apply -f config/crd/asterisk-crd.yaml -f config/crd/platform-crds.yaml
uv run kopf run kubevoip/main.py --namespace telephony --verbose
```

## Release Scope

Releases publish multi-architecture operator, Asterisk, Asterisk-worker,
Kamailio, and RTPengine images plus the OCI Helm chart. Asterisk 22 LTS,
Kamailio 5.6.3, and RTPengine 10.5.3.5 are pinned for v0.2.

Helm intentionally leaves CRDs installed on uninstall. Remove the old
`asterisks.kubevoip.io` CRD only after migration has been verified.

## License

MIT

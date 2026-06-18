<p align="center">
  <img src="assets/logo.svg" alt="KubeVoIP logo" width="220">
</p>

# KubeVoIP

[![Test](https://github.com/kubevoip/kubevoip/actions/workflows/test.yaml/badge.svg)](https://github.com/kubevoip/kubevoip/actions/workflows/test.yaml)
[![Integration](https://github.com/kubevoip/kubevoip/actions/workflows/integration.yaml/badge.svg)](https://github.com/kubevoip/kubevoip/actions/workflows/integration.yaml)

KubeVoIP is a Kubernetes operator for SIP platforms. It runs Kamailio gateways,
RTPengine media relays, SIP users, dial policies, and Asterisk application pods.
PostgreSQL stores registrations, routes, policies, and trunk data.

Project home: [https://kubevoip.com](https://kubevoip.com)

The Helm chart pins tested runtime images from `kubevoip-kamailio`,
`kubevoip-rtpengine`, and `kubevoip-asterisk`.

## Install

```bash
helm install kubevoip oci://ghcr.io/kubevoip/charts/kubevoip \
  --version 0.4.3 \
  --namespace telephony --create-namespace
```

Each Helm release watches only its installation namespace. The ServiceAccount
uses a namespaced Role, including Secret access in that namespace. Install a
separate release for each telephony namespace:

```bash
helm install kubevoip-home oci://ghcr.io/kubevoip/charts/kubevoip \
  --version 0.4.3 --namespace telephony-home --create-namespace
helm install kubevoip-office oci://ghcr.io/kubevoip/charts/kubevoip \
  --version 0.4.3 --namespace telephony-office --create-namespace
```

CRDs remain cluster-scoped Kubernetes resources shared by all releases.

## Quickstart

This quickstart creates a SIP platform with two users: `alice` on extension
`100` and `bob` on extension `101`. It assumes your cluster can provision UDP
`LoadBalancer` Services. It includes a single-pod PostgreSQL Deployment for
testing, so you do not need to choose a production database first.

```bash
helm install kubevoip oci://ghcr.io/kubevoip/charts/kubevoip \
  --version 0.4.3 \
  --namespace telephony --create-namespace

kubectl apply -f examples/quickstart-two-phones.yaml
kubectl -n telephony rollout status deployment/postgres --timeout=180s
kubectl -n telephony wait --for=create deployment/main-sip-gateway --timeout=180s
kubectl -n telephony rollout status deployment/main-sip-gateway --timeout=240s
kubectl -n telephony wait --for=condition=Ready sipuser/alice sipuser/bob --timeout=180s
kubectl -n telephony wait --for=condition=Ready callroute/user-100 callroute/user-101 --timeout=180s
kubectl -n telephony get service main-sip-gateway main-rtpengine-0
```

Register two SIP clients against the external address assigned to the
`main-sip-gateway` Service:

| Phone | SIP username | Password | Extension |
| --- | --- | --- | --- |
| Alice | `alice` | `alice-demo-password` | `100` |
| Bob | `bob` | `bob-demo-password` | `101` |

Alice can call Bob at `101`; Bob can call Alice at `100`.

The quickstart also creates one RTPengine `LoadBalancer` Service for media.
Your network must allow UDP `5060` to the gateway address and UDP
`20000-20049` to the RTPengine address. Do not translate SIP or RTP ports.
See [docs/networking.md](docs/networking.md) for the networking details.

## APIs

- `NetworkProfile`: shared external addressing and local network policy.
- `CallScope`: a searchable bucket of call routes, such as internal or external.
- `DialPolicy`: an ordered list of scopes a caller is allowed to search.
- `SIPUser`: a PostgreSQL-backed identity registered through Kamailio.
- `SIPTrunk`: provider-neutral inbound and outbound trunk policy.
- `CallRoute`: ordered call routing to users, trunks, or AsteriskPool targets.
- `MediaRelay`: stable, horizontally scalable RTPengine replicas.
- `AsteriskPool`: private Asterisk application pods, currently providing Echo.
- `SIPGateway`: Kamailio registration and media-relay edge policy.

Platform resources are experimental. References are namespace-local.

A PostgreSQL database and a standard connection Secret must exist before you
create `SIPGateway` and `SIPUser` resources. KubeVoIP does not install or
require CNPG. The Secret keys are `host`, `port`, `dbname`, `user`, and
`password`. `SIPTrunk` resources read trunk credentials and outbound caller ID
values from Secrets. Keep those values out of ConfigMaps and Git.

Kamailio reads users, trunks, routes, scopes, and dial policies from
PostgreSQL at request time. Normal changes to `SIPUser`, `SIPTrunk`,
`CallRoute`, `CallScope`, and `DialPolicy` update database rows and do not roll
Kamailio pods. Static gateway/network changes can still roll pods.

## External networking

Set `NetworkProfile.spec.externalAddress.value` to an IP address or hostname,
or set `source: Service` to discover addresses from managed LoadBalancer
Services. Component overrides and RTPengine replica overrides take precedence.

KubeVoIP rewrites SIP advertised addresses and RTPengine SDP addresses. Public
forwarding needs identical public and private UDP ports: SIP `5060` and each
assigned RTPengine range. The user is responsible for provider load balancers,
firewall rules, DNS, router forwarding, and trunk configuration.

`Service` and `HostNetwork` media modes are experimental. UDP SIP is the only
supported transport. TLS, WebRTC, and active-call failover are not included. A
namespace and its dedicated operator release form the supported isolation
boundary.

IP-authenticated inbound trunks declare `SIPTrunk.spec.inbound.allowedSourceCidrs`.
Calls arriving from those networks bypass subscriber authentication and use the
trunk's inbound `DialPolicy`. Other INVITEs must authenticate as a `SIPUser`
and use the user's `DialPolicy`. `CallRoute` resources can target a
`sipUserRef`, `asteriskPoolRef`, or `trunkRef`. Outbound trunks can present
caller ID and answer provider digest challenges. KubeVoIP converts digest
passwords to realm-bound HA1 values and stores them in PostgreSQL. Treat HA1 as
credential-equivalent secret material.

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
kubectl apply --dry-run=server -f config/crd/platform-crds.yaml
```

Run the controller against the current cluster:

```bash
kubectl apply -f config/crd/platform-crds.yaml
uv run kopf run kubevoip/main.py --namespace telephony --verbose
```

## Release scope

Releases publish multi-architecture operator, Asterisk, Kamailio, and RTPengine
images plus the OCI Helm chart. The chart pins tested runtime image versions.

Helm leaves CRDs installed on uninstall.

## License

MIT

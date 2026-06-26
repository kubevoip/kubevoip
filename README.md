<p align="center">
  <img src="assets/logo.svg" alt="KubeVoIP logo" width="220">
</p>

# KubeVoIP

[![Test](https://github.com/kubevoip/kubevoip/actions/workflows/test.yaml/badge.svg)](https://github.com/kubevoip/kubevoip/actions/workflows/test.yaml)
[![Integration](https://github.com/kubevoip/kubevoip/actions/workflows/integration.yaml/badge.svg)](https://github.com/kubevoip/kubevoip/actions/workflows/integration.yaml)

KubeVoIP is a Kubernetes operator for SIP platforms. It runs Kamailio gateways,
RTPengine media relays, SIP users, dial policies, provider-neutral trunks, and
Asterisk application pods, with runtime data stored in PostgreSQL. Managed
workloads emit vendor-neutral SIP/RTP logs to Kubernetes container streams, and
SIP gateways can optionally export HEP capture traffic to HOMER-compatible
collectors.

- Website: [kubevoip.com](https://kubevoip.com)
- Documentation: [docs.kubevoip.com](https://docs.kubevoip.com)
- Releases: [github.com/kubevoip/kubevoip/releases](https://github.com/kubevoip/kubevoip/releases)
- Security: [SECURITY.md](SECURITY.md)

## Install

```bash
helm install kubevoip oci://ghcr.io/kubevoip/charts/kubevoip \
  --version 0.6.5 \
  --namespace telephony --create-namespace
```

Each Helm release watches only its installation namespace. CRDs remain
cluster-scoped Kubernetes resources shared by all releases.

Operator failover HA is opt-in. It runs multiple active/passive Kopf operator
pods with a namespace-scoped `KopfPeering` object so only one pod reconciles at
a time, provided generated priorities do not collide:

```bash
helm upgrade --install kubevoip oci://ghcr.io/kubevoip/charts/kubevoip \
  --version 0.6.5 \
  --namespace telephony --create-namespace \
  --set operator.highAvailability.enabled=true \
  --set operator.replicas=3
```

This improves controller availability only; configure the SIP gateway, media
relay, Asterisk workers, and PostgreSQL separately for platform HA. Kopf
peering CRDs are cluster-scoped Kubernetes resources shared by all KubeVoIP
releases, while each release creates its own namespaced `KopfPeering`.

## Observability

KubeVoIP gives operators useful logs without requiring a bundled logging stack:

- Kamailio writes safe `kubevoip_sip_event` summary lines for registrations,
  invites, routing decisions, relay failures, and RTPengine offer/answer steps.
- Kamailio can optionally write raw SIP headers and SDP bodies to stdout with
  the `kubevoip_sip_message` marker for deep provider troubleshooting.
- RTPengine runs in the foreground with stderr logging and emits a
  `kubevoip_rtp_event` startup line for each media relay replica.
- Asterisk workers mount an explicit console logger configuration.
- Optional HOMER support sends SIP capture traffic from Kamailio to a
  user-owned HOMER, heplify-server, or HEP-compatible collector.

Enable HOMER capture on a gateway by setting `SIPGateway.spec.observability`:

```yaml
observability:
  sipHeaders:
    enabled: true
  sdp:
    enabled: true
  capture:
    enabled: true
    type: Homer
    hepAddress: homer-heplify.telemetry.svc.cluster.local
    hepPort: 9060
    hepTransport: udp
    captureMode: transaction
    includePayload: true
```

SIP header logging, SDP body logging, and HOMER capture are off by default
because SIP headers, full SIP payloads, and SDP can contain caller identity,
endpoint addresses, routing metadata, media addresses, authorization headers,
and other sensitive customer information. See
[Observability](docs/observability.md) for log fields, capture modes, and
troubleshooting examples.

## Quickstart

The quickstart creates a small SIP platform with two users: `alice` on
extension `100` and `bob` on extension `101`. It includes a single-pod
PostgreSQL database for testing and assumes your cluster can provision UDP
`LoadBalancer` Services.

```bash
helm install kubevoip oci://ghcr.io/kubevoip/charts/kubevoip \
  --version 0.6.5 \
  --namespace telephony --create-namespace

uvx kubevoip -n telephony init

kubectl -n telephony rollout status deployment/postgres --timeout=180s
kubectl -n telephony rollout status deployment/main-sip-gateway --timeout=240s
kubectl -n telephony wait --for=condition=Ready sipuser/alice sipuser/bob --timeout=180s
kubectl -n telephony get service main-sip-gateway main-rtpengine-0
```

To use your own PostgreSQL database instead of the demo Deployment, skip
the demo database setup and let `init` create the connection Secret:

```bash
printf '%s' "$POSTGRES_PASSWORD" | uvx kubevoip -n telephony init \
  --database existing \
  --postgres-host "$POSTGRES_HOST" \
  --postgres-db kubevoip \
  --postgres-user kubevoip \
  --postgres-password-stdin
```

Register two SIP clients against the external address assigned to
`main-sip-gateway`:

| Phone | SIP username | Password | Extension |
| --- | --- | --- | --- |
| Alice | `alice` | `alice-demo-password` | `100` |
| Bob | `bob` | `bob-demo-password` | `101` |

Alice can call Bob at `101`; Bob can call Alice at `100`.

For the full walkthrough, cleanup steps, networking notes, and production
database guidance, see the [KubeVoIP documentation](https://docs.kubevoip.com).

## Documentation

- [Getting started](https://docs.kubevoip.com/getting-started/quickstart/)
- [Concepts](https://docs.kubevoip.com/concepts/platform-resources/)
- [Networking](https://docs.kubevoip.com/networking/sip-on-kubernetes/)
- [Observability](docs/observability.md)
- [Operations](https://docs.kubevoip.com/operations/postgresql/)
- [API reference](https://docs.kubevoip.com/reference/api/)
- [Contributing](CONTRIBUTING.md)

## Development

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest
helm lint charts/kubevoip
helm template kubevoip charts/kubevoip
kubectl apply --dry-run=server -f config/crd/platform-crds.yaml
```

Run the controller against a development cluster:

```bash
kubectl apply -f config/crd/platform-crds.yaml
uv run kopf run kubevoip/main.py --namespace telephony --verbose
```

## License

MIT

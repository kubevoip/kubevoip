<p align="center">
  <img src="assets/logo.svg" alt="KubeVoIP logo" width="220">
</p>

# KubeVoIP

[![Test](https://github.com/kubevoip/kubevoip/actions/workflows/test.yaml/badge.svg)](https://github.com/kubevoip/kubevoip/actions/workflows/test.yaml)
[![Integration](https://github.com/kubevoip/kubevoip/actions/workflows/integration.yaml/badge.svg)](https://github.com/kubevoip/kubevoip/actions/workflows/integration.yaml)

KubeVoIP is a Kubernetes operator for SIP platforms. It runs Kamailio gateways,
RTPengine media relays, SIP users, dial policies, provider-neutral trunks, and
Asterisk application pods, with runtime data stored in PostgreSQL.

- Website: [kubevoip.com](https://kubevoip.com)
- Documentation: [docs.kubevoip.com](https://docs.kubevoip.com)
- Releases: [github.com/kubevoip/kubevoip/releases](https://github.com/kubevoip/kubevoip/releases)
- Security: [SECURITY.md](SECURITY.md)

## Install

```bash
helm install kubevoip oci://ghcr.io/kubevoip/charts/kubevoip \
  --version 0.5.0 \
  --namespace telephony --create-namespace
```

Each Helm release watches only its installation namespace. CRDs remain
cluster-scoped Kubernetes resources shared by all releases.

## Quickstart

The quickstart creates a small SIP platform with two users: `alice` on
extension `100` and `bob` on extension `101`. It includes a single-pod
PostgreSQL database for testing and assumes your cluster can provision UDP
`LoadBalancer` Services.

```bash
helm install kubevoip oci://ghcr.io/kubevoip/charts/kubevoip \
  --version 0.5.0 \
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

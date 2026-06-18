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
`LoadBalancer` Services. Use the CLI for the SIP users and call routing:

```bash
helm install kubevoip oci://ghcr.io/kubevoip/charts/kubevoip \
  --version 0.5.0 \
  --namespace telephony --create-namespace

kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Secret
metadata:
  name: postgres-app
  namespace: telephony
type: Opaque
stringData:
  host: postgres
  port: "5432"
  dbname: kubevoip
  user: kubevoip
  password: kubevoip-demo-password
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: telephony
spec:
  selector:
    app: kubevoip-demo-postgres
  ports:
    - port: 5432
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: telephony
spec:
  replicas: 1
  selector:
    matchLabels:
      app: kubevoip-demo-postgres
  template:
    metadata:
      labels:
        app: kubevoip-demo-postgres
    spec:
      containers:
        - name: postgres
          image: postgres:16-alpine
          env:
            - name: POSTGRES_DB
              value: kubevoip
            - name: POSTGRES_USER
              value: kubevoip
            - name: POSTGRES_PASSWORD
              value: kubevoip-demo-password
          ports:
            - containerPort: 5432
---
apiVersion: kubevoip.com/v1alpha1
kind: NetworkProfile
metadata:
  name: public
  namespace: telephony
spec:
  externalAddress:
    source: Service
  localNetworks:
    - 10.0.0.0/8
---
apiVersion: kubevoip.com/v1alpha1
kind: MediaRelay
metadata:
  name: main
  namespace: telephony
spec:
  replicas: 1
  networkProfileRef:
    name: public
  media:
    start: 20000
    end: 20049
  network:
    mode: Service
    service:
      type: LoadBalancer
      externalTrafficPolicy: Local
---
apiVersion: kubevoip.com/v1alpha1
kind: SIPGateway
metadata:
  name: main
  namespace: telephony
spec:
  replicas: 1
  databaseSecretRef:
    name: postgres-app
  networkProfileRef:
    name: public
  mediaRelayRef:
    name: main
  service:
    type: LoadBalancer
    externalTrafficPolicy: Local
YAML

printf '%s' 'alice-demo-password' | uvx kubevoip --schema-source cluster -n telephony secret sip-user alice-sip --from-stdin
printf '%s' 'bob-demo-password' | uvx kubevoip --schema-source cluster -n telephony secret sip-user bob-sip --from-stdin
uvx kubevoip --schema-source cluster -n telephony scope create internal --gateway main
uvx kubevoip --schema-source cluster -n telephony policy create internal-only --gateway main --scope internal
uvx kubevoip --schema-source cluster -n telephony user create alice --extension 100 --gateway main --dial-policy internal-only --auth-username alice --caller-id "Alice <100>" --password-secret alice-sip
uvx kubevoip --schema-source cluster -n telephony user create bob --extension 101 --gateway main --dial-policy internal-only --auth-username bob --caller-id "Bob <101>" --password-secret bob-sip
uvx kubevoip --schema-source cluster -n telephony route create user-100 --gateway main --scope internal --priority 100 --match 100 --target-user alice
uvx kubevoip --schema-source cluster -n telephony route create user-101 --gateway main --scope internal --priority 100 --match 101 --target-user bob

kubectl -n telephony rollout status deployment/postgres --timeout=180s
kubectl -n telephony rollout status deployment/main-sip-gateway --timeout=240s
kubectl -n telephony wait --for=condition=Ready sipuser/alice sipuser/bob --timeout=180s
kubectl -n telephony get service main-sip-gateway main-rtpengine-0
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

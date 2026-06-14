# KubeVoIP

[![Test](https://github.com/danohn/kubevoip/actions/workflows/test.yaml/badge.svg)](https://github.com/danohn/kubevoip/actions/workflows/test.yaml)
[![Integration](https://github.com/danohn/kubevoip/actions/workflows/integration.yaml/badge.svg)](https://github.com/danohn/kubevoip/actions/workflows/integration.yaml)

KubeVoIP is a Kubernetes operator that turns an `Asterisk`
custom resource into a single-instance Asterisk PBX. It uses Python, Kopf,
generated static configuration, and ordinary Kubernetes resources.

KubeVoIP v0.1 guarantees cluster-local SIP over UDP. External SIP and RTP
through `LoadBalancer` Services are experimental because NAT, SDP rewriting,
UDP support, and listener limits differ between environments.

## Install

```bash
helm install kubevoip oci://ghcr.io/danohn/charts/kubevoip \
  --version 0.1.0 \
  --namespace kubevoip-system --create-namespace
kubectl apply -f examples/namespace.yaml
kubectl apply -f examples/secret-alice-sip.yaml
kubectl apply -f examples/asterisk-demo.yaml
kubectl -n asterisk-demo get ast,pods,services
```

The operator creates a generated Secret for `pjsip.conf`, a ConfigMap for
`extensions.conf` and `rtp.conf`, a headless Service, one access Service, and a
single-replica StatefulSet. Changing a referenced password Secret is detected
within 30 seconds and rolls the Pod.

## Custom Resource

```yaml
apiVersion: kubevoip.io/v1alpha1
kind: Asterisk
metadata:
  name: demo
  namespace: asterisk-demo
spec:
  service:
    type: ClusterIP
  endpoints:
    - name: alice
      extension: "100"
      passwordSecretRef:
        name: alice-sip
        key: password
  dialplan:
    echoExtension: "600"
```

Endpoint names and numeric extensions must be unique. The echo extension cannot
overlap an endpoint extension. RTP ranges are limited to 200 ports because a
Kubernetes Service requires every UDP port to be listed.

## Development

Requirements: Python 3.12+, `uv`, Helm 3, and access to Kubernetes.

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
helm lint charts/kubevoip
helm template kubevoip charts/kubevoip
```

Run the controller against the current cluster:

```bash
kubectl apply -f config/crd/asterisk-crd.yaml
uv run kopf run kubevoip/main.py --all-namespaces --verbose
```

## Runtime And Networking

`runtime/Dockerfile` builds a pinned Asterisk 22 LTS runtime from source. The
default image is non-root and intentionally includes only modules needed for
PJSIP registration, endpoint calls, RTP, and Echo.

The release publishes `linux/amd64` and `linux/arm64` operator and Asterisk
images. KubeVoIP is tested on a current Kubernetes cluster; older Kubernetes
releases may work but are not part of the v0.1 compatibility guarantee.

The access Service places SIP and RTP on one Kubernetes address. `ClusterIP` is
the supported v0.1 path. A `LoadBalancer` may work on a particular environment,
but portable external calling also requires provider-specific UDP support and
Asterisk NAT/SDP configuration that v0.1 does not manage.

## Release

Tags matching `vX.Y.Z` run tests, build `linux/amd64` and `linux/arm64`
operator/runtime images, publish the Helm chart to GHCR, and create a GitHub
release. Repository, chart, and Python versions must match the tag.

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and
[CHANGELOG.md](CHANGELOG.md) for project policies and release history.

## Cleanup

```bash
kubectl delete -f examples/asterisk-demo.yaml
kubectl delete -f examples/secret-alice-sip.yaml
kubectl delete -f examples/namespace.yaml
helm uninstall kubevoip --namespace kubevoip-system
```

Helm intentionally leaves the CRD installed on uninstall.

## License

MIT

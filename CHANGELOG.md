# Changelog

All notable changes to KubeVoIP are documented in this file.

## [0.2.4] - 2026-06-16

### Fixed

- Outbound trunk calls now rewrite the SIP Request-URI host to the configured
  trunk termination domain before relay.
- Outbound trunk calls can optionally present a caller ID from a deployment
  environment variable while the production caller-ID API is designed.

## [0.2.3] - 2026-06-16

### Fixed

- SIP gateways now advertise separate internal and external Record-Route
  addresses for trunk-to-user calls, including Kamailio aliases and `r2=on`
  route-pair markers so internal phones can tear down dialogs reliably.

## [0.2.2] - 2026-06-15

### Fixed

- Namespace-scoped operator installs now include read-only cluster discovery
  permissions for Namespaces and CRDs, avoiding noisy Kopf startup retries
  without granting cross-namespace Secret access.

## [0.2.1] - 2026-06-15

### Fixed

- LoadBalancer-backed SIP gateways and media relays now create their Services
  before waiting for provider-assigned ingress addresses.
- Pending LoadBalancer address discovery now reports a retrying
  `WaitingForLoadBalancer` condition.

### Changed

- Operator installations are namespace-scoped and use a Role and RoleBinding.
  Install one Helm release per managed telephony namespace.

## [0.2.0] - 2026-06-15

### Added

- Experimental `NetworkProfile`, `SIPUser`, `MediaRelay`, `AsteriskPool`, and
  `SIPGateway` APIs.
- Kamailio, userspace RTPengine, PostgreSQL subscriber reconciliation, and
  private Asterisk application workers.
- Explicit, Service-discovered, component-level, and per-relay external
  address handling.
- Safe v0.1 API migration exporter and versioned Kamailio database migration.

### Changed

- API group moved from `kubevoip.io` to `kubevoip.com` as an intentional
  breaking change.

## [0.1.0] - 2026-06-14

### Added

- Namespaced `kubevoip.io/v1alpha1` `Asterisk` custom resource.
- Cluster-wide Kopf operator with deterministic configuration rendering, status
  conditions, and automatic credential rotation.
- Non-root Asterisk 22 LTS runtime for `linux/amd64` and `linux/arm64`.
- Helm OCI installation with cluster-scoped RBAC and CRD.
- Automated authenticated in-cluster SIP echo-call integration test.

### Limitations

- Cluster-local UDP SIP is the supported networking path.
- External SIP/RTP through a `LoadBalancer` is experimental.
- High availability, trunks, TLS, WebRTC, and production NAT handling are not
  included.

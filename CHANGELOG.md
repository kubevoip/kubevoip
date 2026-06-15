# Changelog

All notable changes to KubeVoIP are documented in this file.

## [0.2.0] - Unreleased

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

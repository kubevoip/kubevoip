# Changelog

All notable changes to KubeVoIP are documented in this file.

## [0.4.3] - 2026-06-17

### Changed

- Pin the platform chart to `v0.4.3` runtime images from the split Kamailio,
  RTPengine, and Asterisk repositories.
- Runtime packages now publish with repository-specific OCI source labels so
  GHCR links each image to its component repository.

## [0.4.2] - 2026-06-17

### Changed

- Runtime images now build from separate component repositories:
  `kubevoip-kamailio`, `kubevoip-rtpengine`, and `kubevoip-asterisk`.
- The platform repository now publishes only the operator image and Helm chart.
- The Asterisk runtime image was renamed from `kubevoip-asterisk-worker` to
  `kubevoip-asterisk`.

## [0.4.1] - 2026-06-17

### Changed

- Project ownership moved to `kubevoip/kubevoip`.
- Release images and the OCI Helm chart now publish under `ghcr.io/kubevoip`.

## [0.4.0] - 2026-06-17

### Added

- `CallScope` and `DialPolicy` APIs for route visibility and caller
  authorization.
- PostgreSQL-backed runtime tables for SIP users, trunks, routes, scopes, and
  policies.
- Realm-bound HA1 storage for outbound digest trunks so raw provider passwords
  are not stored in PostgreSQL.

### Changed

- `SIPUser` now requires `dialPolicyRef`.
- `CallRoute` now requires `scopeRef`.
- Trusted inbound `SIPTrunk` CIDRs now require `inbound.dialPolicyRef`.
- Kamailio now looks up route and trunk runtime data from PostgreSQL instead
  of rendering it into ConfigMaps. Normal user, trunk, route, scope, and policy
  changes no longer roll Kamailio pods.

## [0.3.0] - 2026-06-17

### Added

- First-class `SIPTrunk` and `CallRoute` APIs for provider-neutral trunking and
  ordered routing.
- Secret-backed per-trunk caller ID and outbound digest authentication support
  for provider challenge responses.
- Manual v0.3 migration documentation for converting embedded gateway trunks
  and routes into standalone resources.

### Changed

- `SIPGateway.spec.trunks` and `SIPGateway.spec.routes` were removed as an
  intentional alpha API break. Gateways now reconcile same-namespace
  `SIPTrunk` and `CallRoute` resources that reference them.
- Primary docs and integration fixtures now use generic provider terminology
  and example domains.

### Removed

- The global Helm outbound caller ID setting is no longer part of the
  documented platform API.

## [0.2.7] - 2026-06-17

### Added

- RTPengine Deployments now use preferred pod anti-affinity so relay replicas
  are spread across Kubernetes nodes when capacity allows.

## [0.2.6] - 2026-06-16

### Fixed

- Release builds now publish the operator image without reusing cached source
  layers and verify the pushed image contains the AsteriskPool service split
  before creating the multi-architecture release tag.

## [0.2.5] - 2026-06-16

### Fixed

- Asterisk pools now expose a normal internal ClusterIP service for Kamailio
  routing while retaining a separate headless service for StatefulSet identity,
  avoiding stale headless-service DNS during worker replacement.

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
- Versioned Kamailio database migration.

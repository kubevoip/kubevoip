# Security policy

## Supported versions

KubeVoIP is an early-stage project. Only the latest published release
receives security fixes.

## Reporting a vulnerability

Please report vulnerabilities privately through
[GitHub private vulnerability reporting](https://github.com/danohn/kubevoip/security/advisories/new).
Do not open a public issue for an undisclosed vulnerability.

Include affected versions, reproduction steps, impact, and any suggested
mitigation. Reports will be acknowledged as soon as practical.

## Security boundaries

KubeVoIP v0.2 platform APIs and external networking are experimental. UDP SIP
has no transport encryption. Internet exposure, trunk allowlists, firewalling,
denial-of-service protection, credential lifecycle policy, and PostgreSQL
hardening require environment-specific controls.

KubeVoIP reads user and database credentials from Secrets and must not place
them in status, Events, ConfigMaps, or logs. Kubernetes Secret encryption,
external secret management, and access controls remain cluster responsibilities.

Each operator release watches only its installation namespace and uses a
namespaced Role and RoleBinding. Install a dedicated release in every namespace
that contains KubeVoIP resources. The operator can read all Secrets within its
own namespace because Kubernetes RBAC cannot restrict Secret reads by resource
reference or label. Do not place unrelated application Secrets in a telephony
namespace.

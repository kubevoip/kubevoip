# Security Policy

## Supported Versions

KubeVoIP is an early-stage project. Only the latest published release
receives security fixes.

## Reporting A Vulnerability

Please report vulnerabilities privately through
[GitHub private vulnerability reporting](https://github.com/danohn/kubevoip/security/advisories/new).
Do not open a public issue for an undisclosed vulnerability.

Include affected versions, reproduction steps, impact, and any suggested
mitigation. Reports will be acknowledged as soon as practical.

## Security Boundaries

KubeVoIP v0.2 platform APIs and external networking are experimental. UDP SIP
has no transport encryption. Internet exposure, trunk allowlists, firewalling,
denial-of-service protection, credential lifecycle policy, PostgreSQL
hardening, and multi-tenant isolation require environment-specific controls.

KubeVoIP reads user and database credentials from Secrets and must not place
them in status, Events, ConfigMaps, or logs. Kubernetes Secret encryption,
external secret management, and access controls remain cluster responsibilities.

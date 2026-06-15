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

KubeVoIP v0.1 is not a production-grade PBX platform. Cluster-local UDP SIP is
the supported networking path. External exposure, NAT traversal, denial-of-
service protection, credential lifecycle policy, and multi-tenant isolation
require environment-specific controls outside the project.

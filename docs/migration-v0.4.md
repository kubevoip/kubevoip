# Migrating to v0.4

Version 0.4 keeps `kubevoip.com/v1alpha1` but changes the routing API. Routes
now live in `CallScope` buckets, and callers use `DialPolicy` resources to
decide which buckets they may search.

Create scopes and policies before updating users, trunks, and routes:

```yaml
apiVersion: kubevoip.com/v1alpha1
kind: CallScope
metadata:
  name: internal
spec:
  gatewayRef:
    name: home
---
apiVersion: kubevoip.com/v1alpha1
kind: CallScope
metadata:
  name: external
spec:
  gatewayRef:
    name: home
---
apiVersion: kubevoip.com/v1alpha1
kind: DialPolicy
metadata:
  name: internal-only
spec:
  gatewayRef:
    name: home
  scopes:
    - name: internal
---
apiVersion: kubevoip.com/v1alpha1
kind: DialPolicy
metadata:
  name: internal-external
spec:
  gatewayRef:
    name: home
  scopes:
    - name: internal
    - name: external
```

Then update callers and routes:

```yaml
apiVersion: kubevoip.com/v1alpha1
kind: SIPUser
metadata:
  name: alice
spec:
  gatewayRef:
    name: home
  dialPolicyRef:
    name: internal-external
  extension: "100"
  authUsername: alice
  passwordSecretRef:
    name: alice-sip
    key: password
---
apiVersion: kubevoip.com/v1alpha1
kind: SIPTrunk
metadata:
  name: provider-primary
spec:
  gatewayRef:
    name: home
  terminationUri: provider.example.net
  inbound:
    allowedSourceCidrs:
      - 203.0.113.0/24
    dialPolicyRef:
      name: internal-only
---
apiVersion: kubevoip.com/v1alpha1
kind: CallRoute
metadata:
  name: outbound-provider
spec:
  gatewayRef:
    name: home
  scopeRef:
    name: external
  priority: 300
  match:
    calledNumber: "+..."
  target:
    trunkRef: provider-primary
```

Digest trunks now require `spec.outbound.authentication.digest.realm`. The
operator computes and stores HA1 in PostgreSQL, never the raw password. HA1 is
credential-equivalent for that SIP realm, so protect the application database as
sensitive infrastructure.

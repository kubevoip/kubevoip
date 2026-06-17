# Migrating To v0.3

Version 0.3 keeps `kubevoip.com/v1alpha1` but intentionally changes the
platform API. `SIPGateway.spec.trunks` and `SIPGateway.spec.routes` are removed.
Create separate `SIPTrunk` and `CallRoute` resources in the same namespace as
the gateway.

Before:

```yaml
apiVersion: kubevoip.com/v1alpha1
kind: SIPGateway
metadata:
  name: home
spec:
  trunks:
    - name: provider-primary
      terminationUri: provider.example.net
      allowedSourceCidrs:
        - 203.0.113.0/24
  routes:
    - match:
        calledNumber: "+61..."
      target:
        trunkRef: provider-primary
```

After:

```yaml
apiVersion: kubevoip.com/v1alpha1
kind: SIPGateway
metadata:
  name: home
spec:
  databaseSecretRef:
    name: postgres-app
  networkProfileRef:
    name: public
  mediaRelayRef:
    name: home
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
---
apiVersion: kubevoip.com/v1alpha1
kind: CallRoute
metadata:
  name: outbound-provider
spec:
  gatewayRef:
    name: home
  priority: 300
  match:
    calledNumber: "+61..."
  target:
    trunkRef: provider-primary
```

Prepare the new `SIPTrunk` and `CallRoute` manifests before upgrading. After
the v0.3 CRDs are installed, apply the standalone resources and update each
`SIPGateway` manifest to remove embedded `trunks` and `routes`. v0.3 does not
reconcile embedded gateway trunk or route fields.

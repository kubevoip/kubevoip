# Migrating From v0.1

Version 0.2 moves `Asterisk` from `kubevoip.io/v1alpha1` to
`kubevoip.com/v1alpha1`. Kubernetes cannot change an existing resource's API
group in place.

Install the v0.2 chart, then export clean v0.2 manifests without changing the
existing resources:

```bash
scripts/migrate-api-group.sh --all-namespaces > asterisks-v0.2.yaml
kubectl apply --dry-run=server -f asterisks-v0.2.yaml
kubectl apply -f asterisks-v0.2.yaml
```

The exporter removes status, finalizers, owner references, server metadata,
Argo CD tracking annotations, Kopf annotations, and kubectl bookkeeping. It
preserves specs, user labels, and unrelated annotations.

Verify each new resource and its owned workloads before deleting its v0.1
counterpart. Remove `asterisks.kubevoip.io` only after every namespace has been
migrated and the old resources are no longer required.

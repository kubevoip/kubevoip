import base64

from kubevoip.controller import reconcile

BODY = {
    "apiVersion": "kubevoip.com/v1alpha1",
    "kind": "Asterisk",
    "metadata": {"name": "demo", "namespace": "test", "uid": "uid", "generation": 2},
}


class FakeKubernetes:
    def __init__(self):
        self.applied = []

    def read_secret(self, namespace, name, key):
        return base64.b64decode(base64.b64encode(b"password")).decode()

    def apply(self, resource):
        self.applied.append(resource)

    def ready_replicas(self, namespace, name):
        return 1


def test_reconcile_is_idempotent():
    api = FakeKubernetes()
    spec = {"endpoints": [{"name": "alice", "extension": "100", "passwordSecretRef": {"name": "alice", "key": "password"}}]}
    first = reconcile(BODY, spec, api)
    first_resources = api.applied.copy()
    api.applied.clear()
    second = reconcile(BODY, spec, api)
    assert first["configHash"] == second["configHash"]
    assert first_resources == api.applied
    assert second["phase"] == "Ready"

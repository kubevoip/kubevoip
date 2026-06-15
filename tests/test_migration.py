import importlib.util
from pathlib import Path


def migration_module():
    path = Path(__file__).parents[1] / "scripts/migrate-api-group.py"
    spec = importlib.util.spec_from_file_location("migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_export_removes_server_and_controller_metadata():
    item = {
        "apiVersion": "kubevoip.io/v1alpha1",
        "kind": "Asterisk",
        "metadata": {
            "name": "home",
            "namespace": "voice",
            "resourceVersion": "42",
            "finalizers": ["kopf.zalando.org/KopfFinalizerMarker"],
            "ownerReferences": [{"name": "old"}],
            "labels": {"site": "home"},
            "annotations": {
                "argocd.argoproj.io/tracking-id": "old",
                "kopf.zalando.org/last-handled-configuration": "old",
                "example.com/keep": "yes",
            },
        },
        "spec": {"dialplan": {"echoExtension": "600"}},
        "status": {"phase": "Ready"},
    }
    exported = migration_module().clean(item)
    assert exported["apiVersion"] == "kubevoip.com/v1alpha1"
    assert exported["metadata"] == {
        "name": "home",
        "namespace": "voice",
        "labels": {"site": "home"},
        "annotations": {"example.com/keep": "yes"},
    }
    assert "status" not in exported

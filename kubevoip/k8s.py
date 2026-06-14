"""Kubernetes API interactions."""

import base64
from typing import Any

from kubernetes import client, config
from kubernetes.client import ApiException
from kubernetes.config.config_exception import ConfigException

from kubevoip.config import FIELD_MANAGER


class Kubernetes:
    def __init__(self) -> None:
        try:
            config.load_incluster_config()
        except ConfigException:
            config.load_kube_config()
        self.core = client.CoreV1Api()
        self.apps = client.AppsV1Api()

    def read_secret(self, namespace: str, name: str, key: str) -> str:
        secret = self.core.read_namespaced_secret(name, namespace)
        if not secret.data or key not in secret.data:
            raise KeyError(f"Secret {namespace}/{name} does not contain key {key}")
        return base64.b64decode(secret.data[key]).decode()

    def apply(self, resource: dict[str, Any]) -> None:
        meta = resource["metadata"]
        kwargs = {
            "name": meta["name"],
            "namespace": meta["namespace"],
            "body": resource,
            "field_manager": FIELD_MANAGER,
            "force": True,
            "_content_type": "application/apply-patch+yaml",
        }
        kind = resource["kind"]
        if kind == "Secret":
            self.core.patch_namespaced_secret(**kwargs)
        elif kind == "ConfigMap":
            self.core.patch_namespaced_config_map(**kwargs)
        elif kind == "Service":
            self.core.patch_namespaced_service(**kwargs)
        elif kind == "StatefulSet":
            self.apps.patch_namespaced_stateful_set(**kwargs)
        else:
            raise ValueError(f"unsupported resource kind: {kind}")

    def ready_replicas(self, namespace: str, name: str) -> int:
        try:
            item = self.apps.read_namespaced_stateful_set_status(name, namespace)
        except ApiException as error:
            if error.status == 404:
                return 0
            raise
        return item.status.ready_replicas or 0

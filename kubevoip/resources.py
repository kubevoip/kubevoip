"""Pure Kubernetes object builders."""

import base64
from typing import Any

from kubevoip.models import AsteriskSpec


def resource_names(name: str) -> dict[str, str]:
    base = f"{name}-asterisk"
    return {
        "statefulset": base,
        "headless_service": f"{base}-headless",
        "service": base,
        "pjsip_secret": f"{base}-pjsip",
        "configmap": f"{base}-config",
    }


def labels(name: str) -> dict[str, str]:
    return {
        "app.kubernetes.io/name": "asterisk",
        "app.kubernetes.io/instance": name,
        "app.kubernetes.io/managed-by": "kubevoip",
        "app.kubernetes.io/part-of": "kubevoip",
    }


def owner_reference(body: dict[str, Any]) -> list[dict[str, Any]]:
    meta = body["metadata"]
    return [{
        "apiVersion": body["apiVersion"],
        "kind": body["kind"],
        "name": meta["name"],
        "uid": meta["uid"],
        "controller": True,
        "blockOwnerDeletion": True,
    }]


def metadata(name: str, namespace: str, instance: str, owner: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "namespace": namespace,
        "labels": labels(instance),
        "ownerReferences": owner_reference(owner),
    }


def build_resources(
    name: str,
    namespace: str,
    owner: dict[str, Any],
    spec: AsteriskSpec,
    configs: dict[str, str],
    checksum: str,
) -> list[dict[str, Any]]:
    names = resource_names(name)
    common = {"namespace": namespace, "instance": name, "owner": owner}
    pod_labels = labels(name)
    ports = [{"name": "sip-udp", "protocol": "UDP", "port": spec.sip.port}]
    ports.extend(
        {"name": f"rtp-{port}", "protocol": "UDP", "port": port}
        for port in range(spec.rtp.start, spec.rtp.end + 1)
    )

    pjsip_secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": metadata(names["pjsip_secret"], **common),
        "type": "Opaque",
        "data": {"pjsip.conf": base64.b64encode(configs["pjsip.conf"].encode()).decode()},
    }
    configmap = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": metadata(names["configmap"], **common),
        "data": {
            "extensions.conf": configs["extensions.conf"],
            "rtp.conf": configs["rtp.conf"],
        },
    }
    headless = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": metadata(names["headless_service"], **common),
        "spec": {
            "clusterIP": "None",
            "publishNotReadyAddresses": True,
            "selector": pod_labels,
            "ports": [{"name": "sip-udp", "protocol": "UDP", "port": spec.sip.port}],
        },
    }
    service = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": metadata(names["service"], **common),
        "spec": {"type": spec.service.type, "selector": pod_labels, "ports": ports},
    }
    statefulset = {
        "apiVersion": "apps/v1",
        "kind": "StatefulSet",
        "metadata": metadata(names["statefulset"], **common),
        "spec": {
            "replicas": 1,
            "serviceName": names["headless_service"],
            "selector": {"matchLabels": pod_labels},
            "template": {
                "metadata": {
                    "labels": pod_labels,
                    "annotations": {"kubevoip.io/config-hash": checksum},
                },
                "spec": {
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": 1000,
                        "runAsGroup": 1000,
                        "fsGroup": 1000,
                        "fsGroupChangePolicy": "OnRootMismatch",
                    },
                    "containers": [{
                        "name": "asterisk",
                        "image": spec.image,
                        "imagePullPolicy": "IfNotPresent",
                        "ports": [{"name": "sip-udp", "containerPort": spec.sip.port, "protocol": "UDP"}],
                        "readinessProbe": {
                            "exec": {"command": ["asterisk", "-rx", "core show uptime"]},
                            "initialDelaySeconds": 5,
                            "periodSeconds": 10,
                        },
                        "livenessProbe": {
                            "exec": {"command": ["asterisk", "-rx", "core show uptime"]},
                            "initialDelaySeconds": 20,
                            "periodSeconds": 20,
                        },
                        "volumeMounts": [
                            {"name": "pjsip", "mountPath": "/etc/asterisk/pjsip.conf", "subPath": "pjsip.conf", "readOnly": True},
                            {"name": "config", "mountPath": "/etc/asterisk/extensions.conf", "subPath": "extensions.conf", "readOnly": True},
                            {"name": "config", "mountPath": "/etc/asterisk/rtp.conf", "subPath": "rtp.conf", "readOnly": True},
                            {"name": "run", "mountPath": "/var/run/asterisk"},
                            {"name": "log", "mountPath": "/var/log/asterisk"},
                            {"name": "spool", "mountPath": "/var/spool/asterisk"},
                        ],
                    }],
                    "volumes": [
                        {"name": "pjsip", "secret": {"secretName": names["pjsip_secret"], "defaultMode": 288}},
                        {"name": "config", "configMap": {"name": names["configmap"]}},
                        {"name": "run", "emptyDir": {}},
                        {"name": "log", "emptyDir": {}},
                        {"name": "spool", "emptyDir": {}},
                    ],
                },
            },
        },
    }
    return [pjsip_secret, configmap, headless, service, statefulset]

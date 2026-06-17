"""Kubernetes objects for scalable platform resources."""

import base64
from typing import Any

from kubevoip.models import AsteriskPoolSpec, MediaRelaySpec, SIPGatewaySpec
from kubevoip.platform_render import render_kamailio_config, render_worker_configs, stable_hash


def component_labels(component: str, name: str) -> dict[str, str]:
    return {
        "app.kubernetes.io/name": component,
        "app.kubernetes.io/instance": name,
        "app.kubernetes.io/managed-by": "kubevoip",
        "app.kubernetes.io/part-of": "kubevoip",
    }


def owner_reference(body: dict[str, Any]) -> list[dict[str, Any]]:
    meta = body["metadata"]
    return [
        {
            "apiVersion": body["apiVersion"],
            "kind": body["kind"],
            "name": meta["name"],
            "uid": meta["uid"],
            "controller": True,
            "blockOwnerDeletion": True,
        }
    ]


def metadata(name: str, namespace: str, instance: str, owner: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "namespace": namespace,
        "labels": component_labels("kubevoip", instance),
        "ownerReferences": owner_reference(owner),
    }


def preferred_component_anti_affinity(component: str) -> dict[str, Any]:
    return {
        "podAntiAffinity": {
            "preferredDuringSchedulingIgnoredDuringExecution": [
                {
                    "weight": 100,
                    "podAffinityTerm": {
                        "topologyKey": "kubernetes.io/hostname",
                        "labelSelector": {
                            "matchLabels": {
                                "app.kubernetes.io/name": component,
                                "app.kubernetes.io/managed-by": "kubevoip",
                                "app.kubernetes.io/part-of": "kubevoip",
                            }
                        },
                    },
                }
            ]
        }
    }


def partition_range(start: int, end: int, replicas: int) -> list[tuple[int, int]]:
    size, remainder = divmod(end - start + 1, replicas)
    result = []
    current = start
    for index in range(replicas):
        count = size + (1 if index < remainder else 0)
        result.append((current, current + count - 1))
        current += count
    return result


def build_media_relay_services(
    name: str,
    namespace: str,
    owner: dict[str, Any],
    spec: MediaRelaySpec,
) -> list[dict[str, Any]]:
    services = []
    for index, (start, end) in enumerate(partition_range(spec.media.start, spec.media.end, spec.replicas)):
        instance = f"{name}-{index}"
        labels = component_labels("rtpengine", instance)
        service_name = f"{name}-rtpengine-{index}"
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                **metadata(service_name, namespace=namespace, instance=name, owner=owner),
                "annotations": spec.network.service.annotations,
            },
            "spec": {
                "type": spec.network.service.type,
                "selector": labels,
                "ports": [{"name": "control", "port": 2223, "protocol": "UDP"}]
                + [
                    {"name": f"rtp-{port}", "port": port, "protocol": "UDP"}
                    for port in range(start, end + 1)
                ],
            },
        }
        if spec.network.service.type != "ClusterIP":
            service["spec"]["externalTrafficPolicy"] = spec.network.service.external_traffic_policy
        services.append(service)
    return services


def build_media_relay_resources(
    name: str,
    namespace: str,
    owner: dict[str, Any],
    spec: MediaRelaySpec,
    addresses: list[str],
) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    services = build_media_relay_services(name, namespace, owner, spec)
    for index, ((start, end), address, service) in enumerate(
        zip(
            partition_range(spec.media.start, spec.media.end, spec.replicas),
            addresses,
            services,
            strict=True,
        )
    ):
        instance = f"{name}-{index}"
        labels = component_labels("rtpengine", instance)
        common = {"namespace": namespace, "instance": name, "owner": owner}
        service_name = f"{name}-rtpengine-{index}"
        command = f"""advertised="$(getent ahostsv4 "$EXTERNAL_ADDRESS" | awk 'NR == 1 {{ print $1 }}')"
test -n "$advertised"
exec rtpengine --foreground --log-stderr --table=-1 \
  --interface="$POD_IP!$advertised" --listen-ng=0.0.0.0:2223 \
  --port-min={start} --port-max={end}
"""
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": metadata(service_name, **common),
            "spec": {
                "replicas": 1,
                "selector": {"matchLabels": labels},
                "template": {
                    "metadata": {"labels": labels, "annotations": {"kubevoip.com/external-address": address}},
                    "spec": {
                        "affinity": preferred_component_anti_affinity("rtpengine"),
                        "hostNetwork": spec.network.mode == "HostNetwork",
                        "dnsPolicy": "ClusterFirstWithHostNet" if spec.network.mode == "HostNetwork" else "ClusterFirst",
                        "containers": [
                            {
                                "name": "rtpengine",
                                "image": spec.image,
                                "command": ["sh", "-ec"],
                                "args": [command],
                                "env": [
                                    {"name": "EXTERNAL_ADDRESS", "value": address},
                                    {"name": "POD_IP", "valueFrom": {"fieldRef": {"fieldPath": "status.podIP"}}},
                                ],
                                "ports": [{"name": "control", "containerPort": 2223, "protocol": "UDP"}],
                                "readinessProbe": {"exec": {"command": ["sh", "-c", "kill -0 1"]}, "periodSeconds": 10},
                            }
                        ],
                    },
                },
            },
        }
        resources.extend([service, deployment])
    return resources


def build_asterisk_pool_resources(name: str, namespace: str, owner: dict[str, Any], spec: AsteriskPoolSpec) -> list[dict[str, Any]]:
    base = f"{name}-asterisk-pool"
    headless_name = f"{base}-headless"
    labels = component_labels("asterisk-worker", name)
    common = {"namespace": namespace, "instance": name, "owner": owner}
    configs = render_worker_configs(spec)
    checksum = stable_hash(configs)
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": metadata(f"{base}-config", **common),
        "data": {key: base64.b64encode(value.encode()).decode() for key, value in configs.items()},
    }
    service_ports = [{"name": "sip", "port": 5060, "protocol": "UDP"}]
    service = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": metadata(base, **common),
        "spec": {"type": "ClusterIP", "selector": labels, "ports": service_ports},
    }
    headless = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": metadata(headless_name, **common),
        "spec": {"clusterIP": "None", "selector": labels, "ports": service_ports},
    }
    statefulset = {
        "apiVersion": "apps/v1",
        "kind": "StatefulSet",
        "metadata": metadata(base, **common),
        "spec": {
            "replicas": spec.replicas,
            "serviceName": headless_name,
            "selector": {"matchLabels": labels},
            "template": {
                "metadata": {"labels": labels, "annotations": {"kubevoip.com/config-hash": checksum}},
                "spec": {
                    "containers": [
                        {
                            "name": "asterisk",
                            "image": spec.image,
                            "volumeMounts": [
                                {
                                    "name": "config",
                                    "mountPath": f"/etc/asterisk/{filename}",
                                    "subPath": filename,
                                    "readOnly": True,
                                }
                                for filename in configs
                            ],
                            "readinessProbe": {"exec": {"command": ["asterisk", "-rx", "core show uptime"]}, "periodSeconds": 10},
                        }
                    ],
                    "volumes": [{"name": "config", "secret": {"secretName": f"{base}-config"}}],
                },
            },
        },
    }
    return [secret, service, headless, statefulset]


def build_gateway_service(
    name: str,
    namespace: str,
    owner: dict[str, Any],
    spec: SIPGatewaySpec,
) -> dict[str, Any]:
    base = f"{name}-sip-gateway"
    service = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            **metadata(base, namespace=namespace, instance=name, owner=owner),
            "annotations": spec.service.annotations,
        },
        "spec": {
            "type": spec.service.type,
            "selector": component_labels("kamailio", name),
            "ports": [{"name": "sip-udp", "port": 5060, "protocol": "UDP"}],
        },
    }
    if spec.service.type != "ClusterIP":
        service["spec"]["externalTrafficPolicy"] = spec.service.external_traffic_policy
    return service


def build_gateway_resources(
    name: str,
    namespace: str,
    owner: dict[str, Any],
    spec: SIPGatewaySpec,
    external_address: str,
    internal_address: str,
    relay_endpoints: list[str],
) -> list[dict[str, Any]]:
    base = f"{name}-sip-gateway"
    labels = component_labels("kamailio", name)
    common = {"namespace": namespace, "instance": name, "owner": owner}
    config = render_kamailio_config(spec, name, namespace, external_address, internal_address, relay_endpoints)
    checksum = stable_hash({"kamailio.cfg": config})
    configmap = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": metadata(f"{base}-config", **common), "data": {"kamailio.cfg": config}}
    service = build_gateway_service(name, namespace, owner, spec)
    env = [{"secretRef": {"name": spec.database_secret_ref.name}}]
    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": metadata(base, **common),
        "spec": {
            "replicas": spec.replicas,
            "selector": {"matchLabels": labels},
            "template": {
                "metadata": {"labels": labels, "annotations": {"kubevoip.com/config-hash": checksum}},
                "spec": {
                    "containers": [
                        {
                            "name": "kamailio",
                            "image": spec.image,
                            "envFrom": env,
                            "volumeMounts": [{"name": "config", "mountPath": "/etc/kamailio/kamailio.cfg", "subPath": "kamailio.cfg"}],
                            "readinessProbe": {"exec": {"command": ["sh", "-c", "pgrep kamailio >/dev/null"]}, "periodSeconds": 10},
                        }
                    ],
                    "volumes": [{"name": "config", "configMap": {"name": f"{base}-config"}}],
                },
            },
        },
    }
    return [configmap, service, deployment]

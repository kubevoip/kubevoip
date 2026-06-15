"""Reconciliation orchestration."""

from typing import Any

from kubernetes.client import ApiException
from pydantic import ValidationError

from kubevoip.k8s import Kubernetes
from kubevoip.models import AsteriskSpec, ResolvedEndpoint
from kubevoip.render import config_hash, render_configs
from kubevoip.resources import build_resources, resource_names
from kubevoip.status import success_status


class InvalidSpecError(Exception):
    pass


class DependencyError(Exception):
    pass


class WaitingForLoadBalancerError(DependencyError):
    pass


def reconcile(
    body: dict[str, Any], raw_spec: dict[str, Any], kubernetes: Kubernetes
) -> dict[str, Any]:
    try:
        spec = AsteriskSpec.model_validate(raw_spec)
    except ValidationError as error:
        raise InvalidSpecError(str(error)) from error

    namespace = body["metadata"]["namespace"]
    name = body["metadata"]["name"]
    endpoints: list[ResolvedEndpoint] = []
    try:
        for endpoint in spec.endpoints:
            password = kubernetes.read_secret(
                namespace, endpoint.password_secret_ref.name, endpoint.password_secret_ref.key
            )
            endpoints.append(ResolvedEndpoint(
                name=endpoint.name,
                extension=endpoint.extension,
                password=password,
                caller_id=endpoint.caller_id or f"{endpoint.name} <{endpoint.extension}>",
            ))
    except (ApiException, KeyError, UnicodeDecodeError) as error:
        raise DependencyError(str(error)) from error

    configs = render_configs(spec, endpoints)
    checksum = config_hash(configs)
    for resource in build_resources(name, namespace, body, spec, configs, checksum):
        kubernetes.apply(resource)
    ready = kubernetes.ready_replicas(namespace, resource_names(name)["statefulset"])
    return success_status(
        body["metadata"].get("generation", 1),
        checksum,
        ready,
        body.get("status", {}).get("conditions"),
    )

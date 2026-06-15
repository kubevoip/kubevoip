"""Reconciliation for scalable SIP platform resources."""

import ipaddress
from typing import Any

from kubernetes.client import ApiException
from pydantic import ValidationError

from kubevoip.controller import DependencyError, InvalidSpecError
from kubevoip.database import database_ready, delete_sip_user, reconcile_sip_user
from kubevoip.k8s import Kubernetes
from kubevoip.models import (
    AsteriskPoolSpec,
    MediaRelaySpec,
    NetworkProfileSpec,
    SIPGatewaySpec,
    SIPUserSpec,
)
from kubevoip.platform_resources import (
    build_asterisk_pool_resources,
    build_gateway_resources,
    build_media_relay_resources,
    partition_range,
)
from kubevoip.status import platform_status


def _model(model, raw_spec):
    try:
        return model.model_validate(raw_spec)
    except ValidationError as error:
        raise InvalidSpecError(str(error)) from error


def _profile(namespace: str, name: str, kubernetes: Kubernetes) -> NetworkProfileSpec:
    try:
        return _model(NetworkProfileSpec, kubernetes.read_custom(namespace, "networkprofiles", name)["spec"])
    except ApiException as error:
        raise DependencyError(f"NetworkProfile {namespace}/{name} is unavailable") from error


def _profile_address(profile: NetworkProfileSpec) -> str | None:
    return profile.external_address.value


def resolve_external_address(
    replica_override: str | None = None,
    component_override: str | None = None,
    profile_address: str | None = None,
    service_address: str | None = None,
) -> tuple[str | None, str]:
    for address, source in (
        (replica_override, "ReplicaOverride"),
        (component_override, "ComponentOverride"),
        (profile_address, "NetworkProfile"),
        (service_address, "Service"),
    ):
        if address:
            return address, source
    return None, "Unresolved"


def _database_secret(namespace: str, name: str, kubernetes: Kubernetes) -> dict[str, str]:
    values = kubernetes.read_secret_values(namespace, name)
    host = values.get("host", "")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if host and "." not in host:
            values["host"] = f"{host}.{namespace}.svc"
    return values


def reconcile_network_profile(body: dict[str, Any], raw_spec: dict[str, Any], _kubernetes: Kubernetes) -> dict[str, Any]:
    spec = _model(NetworkProfileSpec, raw_spec)
    address = _profile_address(spec)
    source = "Explicit" if address else "Service"
    return platform_status(
        body["metadata"].get("generation", 1),
        True,
        "ProfileValid",
        "Network profile is valid",
        {"resolvedAddress": address, "addressSource": source, "localNetworks": spec.local_networks},
        body.get("status", {}).get("conditions"),
        [
            (
                "ExternalAddressResolved",
                bool(address) or source == "Service",
                "ExplicitAddress" if address else "ServiceDiscovery",
                "Explicit external address is resolved" if address else "Dependent components will discover their Service addresses",
            ),
            ("ConfigurationReady", True, "Validated", "Network profile configuration is valid"),
        ],
    )


def reconcile_media_relay(body: dict[str, Any], raw_spec: dict[str, Any], kubernetes: Kubernetes) -> dict[str, Any]:
    spec = _model(MediaRelaySpec, raw_spec)
    namespace, name = body["metadata"]["namespace"], body["metadata"]["name"]
    profile = _profile(namespace, spec.network_profile_ref.name, kubernetes)
    overrides = {item.replica: item.external_address for item in spec.network.replica_overrides}
    addresses: list[str] = []
    relay_status: list[dict[str, Any]] = []
    for index, (start, end) in enumerate(partition_range(spec.media.start, spec.media.end, spec.replicas)):
        service_name = f"{name}-rtpengine-{index}"
        address, source = resolve_external_address(
            overrides.get(index),
            spec.network.external_address,
            _profile_address(profile),
            kubernetes.service_ingress(namespace, service_name),
        )
        if not address and spec.network.mode == "Service" and spec.network.service.type == "ClusterIP":
            address = f"{service_name}.{namespace}.svc.cluster.local"
            source = "ClusterIP"
        if not address:
            raise DependencyError(f"external address for RTPengine replica {index} is unavailable")
        addresses.append(address)
        relay_status.append(
            {
                "replica": index,
                "service": service_name,
                "internalAddress": f"{service_name}.{namespace}.svc.cluster.local",
                "externalAddress": address,
                "addressSource": source,
                "media": {"start": start, "end": end},
            }
        )
    for resource in build_media_relay_resources(name, namespace, body, spec, addresses):
        kubernetes.apply(resource)
    ready = sum(kubernetes.ready_deployment_replicas(namespace, f"{name}-rtpengine-{index}") for index in range(spec.replicas))
    return platform_status(
        body["metadata"].get("generation", 1),
        ready == spec.replicas,
        "ReplicasReady" if ready == spec.replicas else "Reconciling",
        f"{ready}/{spec.replicas} RTPengine replicas are ready",
        {"readyReplicas": ready, "relays": relay_status},
        body.get("status", {}).get("conditions"),
        [
            ("ReferencesResolved", True, "Resolved", "NetworkProfile reference is resolved"),
            ("ExternalAddressResolved", True, "Resolved", "All relay external addresses are resolved"),
            ("ConfigurationReady", True, "Rendered", "RTPengine configuration is rendered"),
            ("ReplicasReady", ready == spec.replicas, "Available" if ready == spec.replicas else "Reconciling", f"{ready}/{spec.replicas} RTPengine replicas are ready"),
        ],
    )


def reconcile_asterisk_pool(body: dict[str, Any], raw_spec: dict[str, Any], kubernetes: Kubernetes) -> dict[str, Any]:
    spec = _model(AsteriskPoolSpec, raw_spec)
    namespace, name = body["metadata"]["namespace"], body["metadata"]["name"]
    for resource in build_asterisk_pool_resources(name, namespace, body, spec):
        kubernetes.apply(resource)
    ready = kubernetes.ready_replicas(namespace, f"{name}-asterisk-pool")
    return platform_status(
        body["metadata"].get("generation", 1),
        ready == spec.replicas,
        "ReplicasReady" if ready == spec.replicas else "Reconciling",
        f"{ready}/{spec.replicas} Asterisk workers are ready",
        {"readyReplicas": ready, "service": f"{name}-asterisk-pool"},
        body.get("status", {}).get("conditions"),
        [
            ("ConfigurationReady", True, "Rendered", "Asterisk worker configuration is rendered"),
            ("ReplicasReady", ready == spec.replicas, "Available" if ready == spec.replicas else "Reconciling", f"{ready}/{spec.replicas} Asterisk workers are ready"),
        ],
    )


def reconcile_gateway(body: dict[str, Any], raw_spec: dict[str, Any], kubernetes: Kubernetes) -> dict[str, Any]:
    spec = _model(SIPGatewaySpec, raw_spec)
    namespace, name = body["metadata"]["namespace"], body["metadata"]["name"]
    profile = _profile(namespace, spec.network_profile_ref.name, kubernetes)
    service_name = f"{name}-sip-gateway"
    address, address_source = resolve_external_address(
        component_override=spec.external_address,
        profile_address=_profile_address(profile),
        service_address=kubernetes.service_ingress(namespace, service_name),
    )
    if not address and spec.service.type == "ClusterIP":
        address = f"{service_name}.{namespace}.svc.cluster.local"
        address_source = "ClusterIP"
    if not address:
        raise DependencyError("SIP gateway external address is unavailable")
    try:
        media = kubernetes.read_custom(namespace, "mediarelays", spec.media_relay_ref.name)
    except ApiException as error:
        raise DependencyError(f"MediaRelay {namespace}/{spec.media_relay_ref.name} is unavailable") from error
    relays = media.get("status", {}).get("relays") or []
    if not relays:
        raise DependencyError("MediaRelay has no resolved relay endpoints")
    relay_endpoints = [f"udp:{item['service']}.{namespace}.svc.cluster.local:2223" for item in relays]
    pool_names = {route.target.asterisk_pool_ref for route in spec.routes if route.target.asterisk_pool_ref}
    asterisk_targets = {pool: f"{pool}-asterisk-pool.{namespace}.svc.cluster.local" for pool in pool_names}
    user_names = {route.target.sip_user_ref for route in spec.routes if route.target.sip_user_ref}
    sip_user_targets = {}
    for user_name in user_names:
        try:
            user = kubernetes.read_custom(namespace, "sipusers", user_name)
            sip_user_targets[user_name] = _model(SIPUserSpec, user["spec"]).auth_username
        except ApiException as error:
            raise DependencyError(f"SIPUser {namespace}/{user_name} is unavailable") from error
    database = _database_secret(namespace, spec.database_secret_ref.name, kubernetes)
    try:
        database_ready(database)
    except Exception as error:
        raise DependencyError("gateway database is unavailable") from error
    for resource in build_gateway_resources(name, namespace, body, spec, address, relay_endpoints, asterisk_targets, sip_user_targets):
        kubernetes.apply(resource)
    ready = kubernetes.ready_deployment_replicas(namespace, service_name)
    return platform_status(
        body["metadata"].get("generation", 1),
        ready == spec.replicas,
        "ReplicasReady" if ready == spec.replicas else "Reconciling",
        f"{ready}/{spec.replicas} Kamailio replicas are ready",
        {"readyReplicas": ready, "resolvedAddress": address, "addressSource": address_source},
        body.get("status", {}).get("conditions"),
        [
            ("ReferencesResolved", True, "Resolved", "Gateway references are resolved"),
            ("DatabaseReady", True, "Connected", "Gateway database is reachable"),
            ("ExternalAddressResolved", True, "Resolved", "Gateway external address is resolved"),
            ("RoutesReady", True, "Validated", f"{len(spec.routes)} routes are configured"),
            ("ConfigurationReady", True, "Rendered", "Kamailio configuration is rendered"),
            ("ReplicasReady", ready == spec.replicas, "Available" if ready == spec.replicas else "Reconciling", f"{ready}/{spec.replicas} Kamailio replicas are ready"),
        ],
    )


def reconcile_sip_user_controller(body: dict[str, Any], raw_spec: dict[str, Any], kubernetes: Kubernetes) -> dict[str, Any]:
    spec = _model(SIPUserSpec, raw_spec)
    namespace, name = body["metadata"]["namespace"], body["metadata"]["name"]
    try:
        gateway = kubernetes.read_custom(namespace, "sipgateways", spec.gateway_ref.name)
        gateway_spec = _model(SIPGatewaySpec, gateway["spec"])
        password = kubernetes.read_secret(namespace, spec.password_secret_ref.name, spec.password_secret_ref.key)
        database = _database_secret(namespace, gateway_spec.database_secret_ref.name, kubernetes)
        reconcile_sip_user(database, namespace, name, spec.auth_username, spec.gateway_ref.name, password, spec.caller_id)
    except (ApiException, KeyError, UnicodeDecodeError) as error:
        raise DependencyError("SIP user dependencies are unavailable") from error
    except Exception as error:
        raise DependencyError("SIP user database reconciliation failed") from error
    return platform_status(
        body["metadata"].get("generation", 1),
        True,
        "SubscriberReady",
        "SIP subscriber is stored in the gateway database",
        {
            "gateway": spec.gateway_ref.name,
            "extension": spec.extension,
            "databaseSecretRef": gateway_spec.database_secret_ref.name,
        },
        body.get("status", {}).get("conditions"),
        [
            ("ReferencesResolved", True, "Resolved", "SIP user references are resolved"),
            ("DatabaseReady", True, "Connected", "Gateway database is reachable"),
            ("ConfigurationReady", True, "Stored", "SIP subscriber is stored"),
        ],
    )


def delete_sip_user_controller(body: dict[str, Any], raw_spec: dict[str, Any], kubernetes: Kubernetes) -> None:
    spec = _model(SIPUserSpec, raw_spec)
    namespace, name = body["metadata"]["namespace"], body["metadata"]["name"]
    try:
        try:
            gateway = kubernetes.read_custom(namespace, "sipgateways", spec.gateway_ref.name)
            database_secret_name = _model(SIPGatewaySpec, gateway["spec"]).database_secret_ref.name
        except ApiException as error:
            database_secret_name = body.get("status", {}).get("databaseSecretRef")
            if error.status != 404 or not database_secret_name:
                raise
        database = _database_secret(namespace, database_secret_name, kubernetes)
        delete_sip_user(database, namespace, name)
    except ApiException as error:
        if error.status != 404:
            raise DependencyError("SIP user database cleanup failed") from error
    except Exception as error:
        raise DependencyError("SIP user database cleanup failed") from error

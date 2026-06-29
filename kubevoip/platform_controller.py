"""Reconciliation for scalable SIP platform resources."""

import ipaddress
from typing import Any

from kubernetes.client import ApiException
from pydantic import ValidationError

from kubevoip.controller import DependencyError, InvalidSpecError, WaitingForLoadBalancerError
from kubevoip.database import (
    database_ready,
    delete_call_route,
    delete_call_scope,
    delete_dial_policy,
    delete_sip_trunk,
    delete_sip_user,
    delete_voicemail_mailbox,
    reconcile_call_route,
    reconcile_call_scope,
    reconcile_dial_policy,
    reconcile_sip_trunk,
    reconcile_sip_user,
    reconcile_voicemail_mailbox,
    trunk_digest_ha1,
)
from kubevoip.k8s import Kubernetes
from kubevoip.models import (
    AsteriskPoolSpec,
    CallRouteSpec,
    CallScopeSpec,
    DialPolicySpec,
    MediaRelaySpec,
    NetworkProfileSpec,
    SIPGatewaySpec,
    SIPTrunkSpec,
    SIPUserSpec,
    VoicemailMailboxSpec,
)
from kubevoip.platform_resources import (
    build_asterisk_pool_resources,
    build_gateway_resources,
    build_gateway_service,
    build_media_relay_resources,
    build_media_relay_services,
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


def _gateway(namespace: str, name: str, kubernetes: Kubernetes) -> tuple[dict[str, Any], SIPGatewaySpec]:
    try:
        gateway = kubernetes.read_custom(namespace, "sipgateways", name)
    except ApiException as error:
        raise DependencyError(f"SIPGateway {namespace}/{name} is unavailable") from error
    return gateway, _model(SIPGatewaySpec, gateway["spec"])


def _gateway_database(namespace: str, name: str, kubernetes: Kubernetes) -> tuple[SIPGatewaySpec, dict[str, str]]:
    _gateway_body, spec = _gateway(namespace, name, kubernetes)
    return spec, _database_secret(namespace, spec.database_secret_ref.name, kubernetes)


def _cleanup_database(body: dict[str, Any], spec: Any, kubernetes: Kubernetes) -> dict[str, str]:
    namespace = body["metadata"]["namespace"]
    secret_name = body.get("status", {}).get("databaseSecretRef", "")
    try:
        gateway_name = spec.gateway_ref.name
        gateway = kubernetes.read_custom(namespace, "sipgateways", gateway_name)
        secret_name = _model(SIPGatewaySpec, gateway["spec"]).database_secret_ref.name
    except Exception as error:
        if not secret_name:
            raise error
    return _database_secret(namespace, secret_name, kubernetes)


def _uid(body: dict[str, Any]) -> str:
    return body["metadata"].get("uid", f"{body['metadata'].get('namespace', '')}/{body['metadata']['name']}")


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
    for service in build_media_relay_services(name, namespace, body, spec):
        kubernetes.apply(service)
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
            if spec.network.service.type == "LoadBalancer":
                raise WaitingForLoadBalancerError(f"waiting for LoadBalancer address for RTPengine replica {index}")
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
    database = None
    if spec.applications.voicemail.enabled:
        if not spec.database_secret_ref:
            raise InvalidSpecError("voicemail requires databaseSecretRef")
        database = _database_secret(namespace, spec.database_secret_ref.name, kubernetes)
        try:
            database_ready(database)
        except Exception as error:
            raise DependencyError("AsteriskPool voicemail database is unavailable") from error
    for resource in build_asterisk_pool_resources(name, namespace, body, spec, database):
        kubernetes.apply(resource)
    ready = kubernetes.ready_replicas(namespace, f"{name}-asterisk-pool")
    return platform_status(
        body["metadata"].get("generation", 1),
        ready == spec.replicas,
        "ReplicasReady" if ready == spec.replicas else "Reconciling",
        f"{ready}/{spec.replicas} Asterisk workers are ready",
        {
            "readyReplicas": ready,
            "service": f"{name}-asterisk-pool",
            **({"databaseSecretRef": spec.database_secret_ref.name} if spec.database_secret_ref else {}),
        },
        body.get("status", {}).get("conditions"),
        [
            (
                "DatabaseReady",
                True,
                "Connected",
                "Voicemail database is reachable and schema is applied",
            )
            if spec.applications.voicemail.enabled
            else ("DatabaseReady", True, "NotRequired", "Voicemail database is not required"),
            ("ConfigurationReady", True, "Rendered", "Asterisk worker configuration is rendered"),
            ("ReplicasReady", ready == spec.replicas, "Available" if ready == spec.replicas else "Reconciling", f"{ready}/{spec.replicas} Asterisk workers are ready"),
        ],
    )


def reconcile_gateway(body: dict[str, Any], raw_spec: dict[str, Any], kubernetes: Kubernetes) -> dict[str, Any]:
    spec = _model(SIPGatewaySpec, raw_spec)
    namespace, name = body["metadata"]["namespace"], body["metadata"]["name"]
    profile = _profile(namespace, spec.network_profile_ref.name, kubernetes)
    service_name = f"{name}-sip-gateway"
    kubernetes.apply(build_gateway_service(name, namespace, body, spec))
    service_address = kubernetes.service_ingress(namespace, service_name)
    address, address_source = resolve_external_address(
        component_override=spec.external_address,
        profile_address=_profile_address(profile),
        service_address=service_address,
    )
    if not address and spec.service.type == "ClusterIP":
        address = f"{service_name}.{namespace}.svc.cluster.local"
        address_source = "ClusterIP"
    if not address:
        if spec.service.type == "LoadBalancer":
            raise WaitingForLoadBalancerError("waiting for LoadBalancer address for SIP gateway")
        raise DependencyError("SIP gateway external address is unavailable")
    internal_address = spec.internal_address or service_address or f"{service_name}.{namespace}.svc.cluster.local"
    try:
        media = kubernetes.read_custom(namespace, "mediarelays", spec.media_relay_ref.name)
    except ApiException as error:
        raise DependencyError(f"MediaRelay {namespace}/{spec.media_relay_ref.name} is unavailable") from error
    relays = media.get("status", {}).get("relays") or []
    if not relays:
        raise DependencyError("MediaRelay has no resolved relay endpoints")
    relay_endpoints = [f"udp:{item['service']}.{namespace}.svc.cluster.local:2223" for item in relays]
    database = _database_secret(namespace, spec.database_secret_ref.name, kubernetes)
    try:
        database_ready(database)
    except Exception as error:
        raise DependencyError("gateway database is unavailable") from error
    for resource in build_gateway_resources(name, namespace, body, spec, address, internal_address, relay_endpoints):
        kubernetes.apply(resource)
    ready = kubernetes.ready_deployment_replicas(namespace, service_name)
    return platform_status(
        body["metadata"].get("generation", 1),
        ready == spec.replicas,
        "ReplicasReady" if ready == spec.replicas else "Reconciling",
        f"{ready}/{spec.replicas} Kamailio replicas are ready",
        {
            "readyReplicas": ready,
            "resolvedAddress": address,
            "addressSource": address_source,
            "internalAddress": internal_address,
            "databaseSecretRef": spec.database_secret_ref.name,
        },
        body.get("status", {}).get("conditions"),
        [
            ("ReferencesResolved", True, "Resolved", "Gateway references are resolved"),
            ("DatabaseReady", True, "Connected", "Gateway database is reachable and schema is applied"),
            ("ExternalAddressResolved", True, "Resolved", "Gateway external address is resolved"),
            ("RuntimeDataReady", True, "DatabaseBacked", "Gateway runtime data is loaded from PostgreSQL"),
            ("ConfigurationReady", True, "Rendered", "Static Kamailio configuration is rendered"),
            ("ReplicasReady", ready == spec.replicas, "Available" if ready == spec.replicas else "Reconciling", f"{ready}/{spec.replicas} Kamailio replicas are ready"),
        ],
    )


def reconcile_call_scope_controller(body: dict[str, Any], raw_spec: dict[str, Any], kubernetes: Kubernetes) -> dict[str, Any]:
    spec = _model(CallScopeSpec, raw_spec)
    namespace, name = body["metadata"]["namespace"], body["metadata"]["name"]
    try:
        gateway_spec, database = _gateway_database(namespace, spec.gateway_ref.name, kubernetes)
        reconcile_call_scope(database, namespace, name, _uid(body), spec.gateway_ref.name)
    except ApiException as error:
        raise DependencyError("Call scope dependencies are unavailable") from error
    except Exception as error:
        raise DependencyError("Call scope database reconciliation failed") from error
    return platform_status(
        body["metadata"].get("generation", 1),
        True,
        "ScopeReady",
        "Call scope is stored in the gateway database",
        {"gateway": spec.gateway_ref.name, "databaseSecretRef": gateway_spec.database_secret_ref.name},
        body.get("status", {}).get("conditions"),
        [
            ("ReferencesResolved", True, "Resolved", "Call scope references are resolved"),
            ("DatabaseReady", True, "Stored", "Call scope is stored"),
        ],
    )


def reconcile_dial_policy_controller(body: dict[str, Any], raw_spec: dict[str, Any], kubernetes: Kubernetes) -> dict[str, Any]:
    spec = _model(DialPolicySpec, raw_spec)
    namespace, name = body["metadata"]["namespace"], body["metadata"]["name"]
    try:
        gateway_spec, database = _gateway_database(namespace, spec.gateway_ref.name, kubernetes)
        for scope in spec.scopes:
            kubernetes.read_custom(namespace, "callscopes", scope.name)
        reconcile_dial_policy(database, namespace, name, _uid(body), spec.gateway_ref.name, [scope.name for scope in spec.scopes])
    except ApiException as error:
        raise DependencyError("Dial policy dependencies are unavailable") from error
    except Exception as error:
        raise DependencyError("Dial policy database reconciliation failed") from error
    return platform_status(
        body["metadata"].get("generation", 1),
        True,
        "PolicyReady",
        "Dial policy is stored in the gateway database",
        {"gateway": spec.gateway_ref.name, "databaseSecretRef": gateway_spec.database_secret_ref.name, "scopes": [scope.name for scope in spec.scopes]},
        body.get("status", {}).get("conditions"),
        [
            ("ReferencesResolved", True, "Resolved", "Dial policy references are resolved"),
            ("DatabaseReady", True, "Stored", "Dial policy is stored"),
        ],
    )


def reconcile_sip_trunk_controller(body: dict[str, Any], raw_spec: dict[str, Any], kubernetes: Kubernetes) -> dict[str, Any]:
    spec = _model(SIPTrunkSpec, raw_spec)
    namespace, name = body["metadata"]["namespace"], body["metadata"]["name"]
    caller_id = None
    digest_username = digest_realm = digest_ha1 = None
    try:
        gateway_spec, database = _gateway_database(namespace, spec.gateway_ref.name, kubernetes)
        if spec.inbound.dial_policy_ref:
            kubernetes.read_custom(namespace, "dialpolicies", spec.inbound.dial_policy_ref.name)
        if spec.outbound.caller_id_secret_ref:
            caller_id = kubernetes.read_secret(namespace, spec.outbound.caller_id_secret_ref.name, spec.outbound.caller_id_secret_ref.key)
        auth = spec.outbound.authentication
        if auth.mode == "Digest" and auth.digest:
            if not auth.digest.realm:
                raise InvalidSpecError("Digest authentication requires digest.realm")
            digest_username = kubernetes.read_secret(namespace, auth.digest.username_secret_ref.name, auth.digest.username_secret_ref.key)
            digest_password = kubernetes.read_secret(namespace, auth.digest.password_secret_ref.name, auth.digest.password_secret_ref.key)
            digest_realm = auth.digest.realm
            digest_ha1 = trunk_digest_ha1(digest_username, digest_realm, digest_password)
        reconcile_sip_trunk(
            database,
            namespace,
            name,
            _uid(body),
            spec.gateway_ref.name,
            spec.termination_uri,
            spec.inbound.allowed_source_cidrs,
            spec.inbound.dial_policy_ref.name if spec.inbound.dial_policy_ref else None,
            caller_id,
            digest_username,
            digest_realm,
            digest_ha1,
        )
    except InvalidSpecError:
        raise
    except (ApiException, KeyError, UnicodeDecodeError) as error:
        raise DependencyError("SIP trunk dependencies are unavailable") from error
    except Exception as error:
        raise DependencyError("SIP trunk database reconciliation failed") from error
    return platform_status(
        body["metadata"].get("generation", 1),
        True,
        "TrunkReady",
        "SIP trunk is stored in the gateway database",
        {
            "gateway": spec.gateway_ref.name,
            "terminationUri": spec.termination_uri,
            "authenticationMode": spec.outbound.authentication.mode,
            "databaseSecretRef": gateway_spec.database_secret_ref.name,
        },
        body.get("status", {}).get("conditions"),
        [
            ("ReferencesResolved", True, "Resolved", "SIP trunk references are resolved"),
            ("DatabaseReady", True, "Stored", "SIP trunk runtime data is stored"),
        ],
    )


def reconcile_call_route_controller(body: dict[str, Any], raw_spec: dict[str, Any], kubernetes: Kubernetes) -> dict[str, Any]:
    spec = _model(CallRouteSpec, raw_spec)
    namespace, name = body["metadata"]["namespace"], body["metadata"]["name"]
    target_kind = target_ref = ""
    target_extension = target_host = None
    try:
        gateway_spec, database = _gateway_database(namespace, spec.gateway_ref.name, kubernetes)
        kubernetes.read_custom(namespace, "callscopes", spec.scope_ref.name)
        if spec.target.sip_user_ref:
            kubernetes.read_custom(namespace, "sipusers", spec.target.sip_user_ref)
            target_kind, target_ref = "SIPUser", spec.target.sip_user_ref
        if spec.target.asterisk_pool_ref:
            kubernetes.read_custom(namespace, "asteriskpools", spec.target.asterisk_pool_ref)
            target_kind, target_ref = "AsteriskPool", spec.target.asterisk_pool_ref
            target_extension = spec.target.extension
            target_host = f"{spec.target.asterisk_pool_ref}-asterisk-pool.{namespace}.svc.cluster.local"
        if spec.target.trunk_ref:
            kubernetes.read_custom(namespace, "siptrunks", spec.target.trunk_ref)
            target_kind, target_ref = "SIPTrunk", spec.target.trunk_ref
        reconcile_call_route(
            database,
            namespace,
            name,
            _uid(body),
            spec.gateway_ref.name,
            spec.scope_ref.name,
            spec.priority,
            spec.match.called_number,
            target_kind,
            target_ref,
            target_extension,
            target_host,
        )
    except ApiException as error:
        raise DependencyError("Call route dependencies are unavailable") from error
    except Exception as error:
        raise DependencyError("Call route database reconciliation failed") from error
    return platform_status(
        body["metadata"].get("generation", 1),
        True,
        "RouteReady",
        "Call route is stored in the gateway database",
        {
            "gateway": spec.gateway_ref.name,
            "scope": spec.scope_ref.name,
            "priority": spec.priority,
            "calledNumber": spec.match.called_number,
            "databaseSecretRef": gateway_spec.database_secret_ref.name,
        },
        body.get("status", {}).get("conditions"),
        [
            ("ReferencesResolved", True, "Resolved", "Call route references are resolved"),
            ("DatabaseReady", True, "Stored", "Call route runtime data is stored"),
        ],
    )


def reconcile_sip_user_controller(body: dict[str, Any], raw_spec: dict[str, Any], kubernetes: Kubernetes) -> dict[str, Any]:
    spec = _model(SIPUserSpec, raw_spec)
    namespace, name = body["metadata"]["namespace"], body["metadata"]["name"]
    try:
        gateway_spec, database = _gateway_database(namespace, spec.gateway_ref.name, kubernetes)
        kubernetes.read_custom(namespace, "dialpolicies", spec.dial_policy_ref.name)
        password = kubernetes.read_secret(namespace, spec.password_secret_ref.name, spec.password_secret_ref.key)
        reconcile_sip_user(
            database,
            namespace,
            name,
            _uid(body),
            spec.auth_username,
            spec.gateway_ref.name,
            spec.extension,
            spec.dial_policy_ref.name,
            password,
            spec.caller_id,
        )
    except (ApiException, KeyError, UnicodeDecodeError) as error:
        raise DependencyError("SIP user dependencies are unavailable") from error
    except Exception as error:
        raise DependencyError("SIP user database reconciliation failed") from error
    return platform_status(
        body["metadata"].get("generation", 1),
        True,
        "SubscriberReady",
        "SIP subscriber and runtime data are stored in the gateway database",
        {
            "gateway": spec.gateway_ref.name,
            "extension": spec.extension,
            "dialPolicy": spec.dial_policy_ref.name,
            "databaseSecretRef": gateway_spec.database_secret_ref.name,
        },
        body.get("status", {}).get("conditions"),
        [
            ("ReferencesResolved", True, "Resolved", "SIP user references are resolved"),
            ("DatabaseReady", True, "Stored", "SIP subscriber and runtime data are stored"),
        ],
    )


def reconcile_voicemail_mailbox_controller(body: dict[str, Any], raw_spec: dict[str, Any], kubernetes: Kubernetes) -> dict[str, Any]:
    spec = _model(VoicemailMailboxSpec, raw_spec)
    namespace, name = body["metadata"]["namespace"], body["metadata"]["name"]
    try:
        user_body = kubernetes.read_custom(namespace, "sipusers", spec.sip_user_ref.name)
        user_spec = _model(SIPUserSpec, user_body["spec"])
        pool_body = kubernetes.read_custom(namespace, "asteriskpools", spec.asterisk_pool_ref.name)
        pool_spec = _model(AsteriskPoolSpec, pool_body["spec"])
        if not pool_spec.applications.voicemail.enabled:
            raise InvalidSpecError(f"AsteriskPool {namespace}/{spec.asterisk_pool_ref.name} does not enable voicemail")
        gateway_spec, database = _gateway_database(namespace, user_spec.gateway_ref.name, kubernetes)
        if not pool_spec.database_secret_ref or pool_spec.database_secret_ref.name != gateway_spec.database_secret_ref.name:
            raise InvalidSpecError("VoicemailMailbox requires SIPUser gateway and AsteriskPool to use the same databaseSecretRef")
        if spec.email.enabled and spec.email.api_key_secret_ref:
            kubernetes.read_secret(namespace, spec.email.api_key_secret_ref.name, spec.email.api_key_secret_ref.key)
        mailbox = spec.mailbox or user_spec.extension
        target_host = f"{spec.asterisk_pool_ref.name}-asterisk-pool.{namespace}.svc.cluster.local"
        reconcile_voicemail_mailbox(
            database,
            namespace,
            name,
            _uid(body),
            user_spec.gateway_ref.name,
            spec.sip_user_ref.name,
            user_spec.auth_username,
            user_spec.extension,
            spec.asterisk_pool_ref.name,
            target_host,
            pool_spec.applications.voicemail.deposit_extension,
            mailbox,
            user_spec.caller_id,
            spec.fallback.enabled,
            spec.fallback.timeout_seconds,
            spec.fallback.on_busy,
            spec.fallback.on_unavailable,
            spec.fallback.on_no_answer,
            spec.email.enabled,
            spec.email.to,
            spec.email.from_address,
            spec.email.provider,
        )
    except InvalidSpecError:
        raise
    except (ApiException, KeyError, UnicodeDecodeError) as error:
        raise DependencyError("VoicemailMailbox dependencies are unavailable") from error
    except Exception as error:
        raise DependencyError("VoicemailMailbox database reconciliation failed") from error
    return platform_status(
        body["metadata"].get("generation", 1),
        True,
        "MailboxReady",
        "Voicemail mailbox is stored in the gateway database",
        {
            "gateway": user_spec.gateway_ref.name,
            "sipUser": spec.sip_user_ref.name,
            "asteriskPool": spec.asterisk_pool_ref.name,
            "mailbox": mailbox,
            "databaseSecretRef": gateway_spec.database_secret_ref.name,
        },
        body.get("status", {}).get("conditions"),
        [
            ("ReferencesResolved", True, "Resolved", "VoicemailMailbox references are resolved"),
            ("DatabaseReady", True, "Stored", "Voicemail mailbox runtime data is stored"),
        ],
    )


def delete_voicemail_mailbox_controller(body: dict[str, Any], raw_spec: dict[str, Any], kubernetes: Kubernetes) -> None:
    spec = _model(VoicemailMailboxSpec, raw_spec)
    namespace = body["metadata"]["namespace"]
    try:
        user_body = kubernetes.read_custom(namespace, "sipusers", spec.sip_user_ref.name)
        user_spec = _model(SIPUserSpec, user_body["spec"])
        _gateway_spec, database = _gateway_database(namespace, user_spec.gateway_ref.name, kubernetes)
    except Exception:
        database = _database_secret(namespace, body.get("status", {}).get("databaseSecretRef", ""), kubernetes)
    delete_voicemail_mailbox(database, namespace, body["metadata"]["name"])


def _delete_runtime_row(body: dict[str, Any], raw_spec: dict[str, Any], kubernetes: Kubernetes, model, delete_func) -> None:
    spec = _model(model, raw_spec)
    namespace, name = body["metadata"]["namespace"], body["metadata"]["name"]
    try:
        database = _cleanup_database(body, spec, kubernetes)
        delete_func(database, namespace, name)
    except ApiException as error:
        if error.status != 404:
            raise DependencyError("runtime database cleanup failed") from error
    except Exception as error:
        raise DependencyError("runtime database cleanup failed") from error


def delete_call_scope_controller(body: dict[str, Any], raw_spec: dict[str, Any], kubernetes: Kubernetes) -> None:
    _delete_runtime_row(body, raw_spec, kubernetes, CallScopeSpec, delete_call_scope)


def delete_dial_policy_controller(body: dict[str, Any], raw_spec: dict[str, Any], kubernetes: Kubernetes) -> None:
    _delete_runtime_row(body, raw_spec, kubernetes, DialPolicySpec, delete_dial_policy)


def delete_sip_trunk_controller(body: dict[str, Any], raw_spec: dict[str, Any], kubernetes: Kubernetes) -> None:
    _delete_runtime_row(body, raw_spec, kubernetes, SIPTrunkSpec, delete_sip_trunk)


def delete_call_route_controller(body: dict[str, Any], raw_spec: dict[str, Any], kubernetes: Kubernetes) -> None:
    _delete_runtime_row(body, raw_spec, kubernetes, CallRouteSpec, delete_call_route)


def delete_sip_user_controller(body: dict[str, Any], raw_spec: dict[str, Any], kubernetes: Kubernetes) -> None:
    _delete_runtime_row(body, raw_spec, kubernetes, SIPUserSpec, delete_sip_user)

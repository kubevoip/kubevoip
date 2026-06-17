"""Kopf entrypoint."""

import kopf
from kubernetes.client import ApiException

from kubevoip.config import GROUP, PLURAL, VERSION
from kubevoip.controller import DependencyError, InvalidSpecError, WaitingForLoadBalancerError, reconcile
from kubevoip.k8s import Kubernetes
from kubevoip.platform_controller import (
    delete_sip_user_controller,
    reconcile_asterisk_pool,
    reconcile_call_route_controller,
    reconcile_gateway,
    reconcile_media_relay,
    reconcile_network_profile,
    reconcile_sip_trunk_controller,
    reconcile_sip_user_controller,
)
from kubevoip.status import error_status, platform_status


def _run(reconciler, body, spec, patch, logger) -> None:
    generation = body["metadata"].get("generation", 1)
    previous = body.get("status", {}).get("conditions")
    try:
        patch.status.update(reconciler(body, spec, Kubernetes()))
    except InvalidSpecError as error:
        patch.status.update(error_status(generation, "InvalidSpec", str(error), previous))
        logger.error("Invalid resource specification: %s", error)
        raise kopf.PermanentError(str(error)) from error
    except WaitingForLoadBalancerError as error:
        patch.status.update(
            platform_status(
                generation,
                False,
                "WaitingForLoadBalancer",
                str(error),
                previous=previous,
                component_conditions=[
                    ("ExternalAddressResolved", False, "WaitingForLoadBalancer", str(error)),
                ],
            )
        )
        raise kopf.TemporaryError(str(error), delay=15) from error
    except DependencyError as error:
        patch.status.update(error_status(generation, "DependencyUnavailable", str(error), previous))
        raise kopf.TemporaryError(str(error), delay=30) from error
    except ApiException as error:
        patch.status.update(error_status(generation, "KubernetesApiError", str(error), previous))
        raise kopf.TemporaryError(str(error), delay=15) from error


@kopf.on.create(GROUP, VERSION, PLURAL)
@kopf.on.update(GROUP, VERSION, PLURAL)
@kopf.on.resume(GROUP, VERSION, PLURAL)
def reconcile_asterisk(body, spec, patch, logger, **_):
    _run(reconcile, body, spec, patch, logger)


@kopf.timer(GROUP, VERSION, PLURAL, interval=30.0, sharp=True)
def refresh_asterisk(body, spec, patch, logger, **_):
    _run(reconcile, body, spec, patch, logger)


def _handlers(plural, reconciler):
    def handler(body, spec, patch, logger, **_):
        _run(reconciler, body, spec, patch, logger)

    kopf.on.create(GROUP, VERSION, plural, id=f"{plural}-create")(handler)
    kopf.on.update(GROUP, VERSION, plural, id=f"{plural}-update")(handler)
    kopf.on.resume(GROUP, VERSION, plural, id=f"{plural}-resume")(handler)
    kopf.timer(GROUP, VERSION, plural, id=f"{plural}-refresh", interval=30.0, sharp=True)(handler)


_handlers("networkprofiles", reconcile_network_profile)
_handlers("mediarelays", reconcile_media_relay)
_handlers("asteriskpools", reconcile_asterisk_pool)
_handlers("sipgateways", reconcile_gateway)
_handlers("siptrunks", reconcile_sip_trunk_controller)
_handlers("callroutes", reconcile_call_route_controller)
_handlers("sipusers", reconcile_sip_user_controller)


@kopf.on.delete(GROUP, VERSION, "sipusers")
def delete_sip_user(body, spec, **_):
    delete_sip_user_controller(body, spec, Kubernetes())

"""Kopf entrypoint."""

import kopf
from kubernetes.client import ApiException

from kubevoip.config import GROUP, PLURAL, VERSION
from kubevoip.controller import DependencyError, InvalidSpecError, reconcile
from kubevoip.k8s import Kubernetes
from kubevoip.status import error_status


def _run(body, spec, patch, logger) -> None:
    generation = body["metadata"].get("generation", 1)
    previous = body.get("status", {}).get("conditions")
    try:
        patch.status.update(reconcile(body, spec, Kubernetes()))
    except InvalidSpecError as error:
        patch.status.update(error_status(generation, "InvalidSpec", str(error), previous))
        logger.error("Invalid Asterisk specification: %s", error)
        raise kopf.PermanentError(str(error)) from error
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
    _run(body, spec, patch, logger)


@kopf.timer(GROUP, VERSION, PLURAL, interval=30.0, sharp=True)
def refresh_asterisk(body, spec, patch, logger, **_):
    _run(body, spec, patch, logger)

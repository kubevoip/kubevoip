"""Custom resource status helpers."""

from datetime import UTC, datetime
from typing import Any


def condition(
    condition_type: str,
    status: str,
    reason: str,
    message: str,
    generation: int,
    previous: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    transition_time = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    for old in previous or []:
        if old.get("type") == condition_type and old.get("status") == status and old.get("reason") == reason and old.get("message") == message:
            transition_time = old.get("lastTransitionTime", transition_time)
            break
    return {
        "type": condition_type,
        "status": status,
        "reason": reason,
        "message": message,
        "observedGeneration": generation,
        "lastTransitionTime": transition_time,
    }


def success_status(
    generation: int,
    checksum: str,
    ready_replicas: int,
    previous: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ready = ready_replicas >= 1
    return {
        "observedGeneration": generation,
        "phase": "Ready" if ready else "Reconciling",
        "ready": ready,
        "configHash": checksum,
        "readyReplicas": ready_replicas,
        "conditions": [
            condition("Ready", "True" if ready else "False", "StatefulSetReady" if ready else "Reconciling", "Asterisk is ready" if ready else "Waiting for the Asterisk Pod", generation, previous),
            condition("ConfigRendered", "True", "Rendered", "Asterisk configuration rendered successfully", generation, previous),
        ],
    }


def error_status(
    generation: int,
    reason: str,
    message: str,
    previous: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "observedGeneration": generation,
        "phase": "Error",
        "ready": False,
        "conditions": [condition("Ready", "False", reason, message, generation, previous)],
    }


def platform_status(
    generation: int,
    ready: bool,
    reason: str,
    message: str,
    details: dict[str, Any] | None = None,
    previous: list[dict[str, Any]] | None = None,
    component_conditions: list[tuple[str, bool, str, str]] | None = None,
) -> dict[str, Any]:
    conditions = [condition("Ready", "True" if ready else "False", reason, message, generation, previous)]
    conditions.extend(
        condition(condition_type, "True" if status else "False", item_reason, item_message, generation, previous) for condition_type, status, item_reason, item_message in component_conditions or []
    )
    return {
        "observedGeneration": generation,
        "phase": "Ready" if ready else "Reconciling",
        "ready": ready,
        **(details or {}),
        "conditions": conditions,
    }

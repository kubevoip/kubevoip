from kubevoip.status import condition


def test_transition_time_is_stable_without_transition():
    first = condition("Ready", "True", "Ready", "Resource is ready", 1)
    second = condition("Ready", "True", "Ready", "Resource is ready", 2, [first])
    assert first["lastTransitionTime"] == second["lastTransitionTime"]

from kubevoip.status import success_status


def test_transition_time_is_stable_without_transition():
    first = success_status(1, "hash", 1)
    second = success_status(2, "hash", 1, first["conditions"])
    assert first["conditions"][0]["lastTransitionTime"] == second["conditions"][0]["lastTransitionTime"]

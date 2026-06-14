import pytest
from pydantic import ValidationError

from kubevoip.models import AsteriskSpec


def test_defaults():
    spec = AsteriskSpec()
    assert spec.service.type == "ClusterIP"
    assert spec.sip.port == 5060
    assert spec.rtp.start == 10000


@pytest.mark.parametrize(
    "raw",
    [
        {"rtp": {"start": 10100, "end": 10000}},
        {"rtp": {"start": 10000, "end": 10300}},
        {"endpoints": [
            {"name": "alice", "extension": "100", "passwordSecretRef": {"name": "one", "key": "password"}},
            {"name": "alice", "extension": "101", "passwordSecretRef": {"name": "two", "key": "password"}},
        ]},
        {"endpoints": [
            {"name": "alice", "extension": "100", "passwordSecretRef": {"name": "one", "key": "password"}},
            {"name": "bob", "extension": "100", "passwordSecretRef": {"name": "two", "key": "password"}},
        ]},
        {"endpoints": [
            {"name": "alice", "extension": "600", "passwordSecretRef": {"name": "one", "key": "password"}},
        ]},
    ],
)
def test_invalid_specs(raw):
    with pytest.raises(ValidationError):
        AsteriskSpec.model_validate(raw)

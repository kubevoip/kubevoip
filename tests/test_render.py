from kubevoip.models import AsteriskSpec, ResolvedEndpoint
from kubevoip.render import config_hash, render_configs


def test_render_and_hash_are_deterministic():
    spec = AsteriskSpec.model_validate({"rtp": {"start": 12000, "end": 12010}})
    endpoints = [ResolvedEndpoint(name="alice", extension="100", password="secret", caller_id="Alice <100>")]
    first = render_configs(spec, endpoints)
    second = render_configs(spec, endpoints)
    assert first == second
    assert "password=secret" in first["pjsip.conf"]
    assert "exten => 100,1,Dial(PJSIP/alice,30)" in first["extensions.conf"]
    assert "rtpstart=12000" in first["rtp.conf"]
    assert config_hash(first) == config_hash(second)


def test_hash_changes_with_secret():
    spec = AsteriskSpec()
    one = render_configs(spec, [ResolvedEndpoint(name="alice", extension="100", password="one", caller_id="Alice <100>")])
    two = render_configs(spec, [ResolvedEndpoint(name="alice", extension="100", password="two", caller_id="Alice <100>")])
    assert config_hash(one) != config_hash(two)

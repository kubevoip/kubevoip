"""Deterministic Asterisk configuration rendering."""

import hashlib

from jinja2 import Environment, PackageLoader, StrictUndefined

from kubevoip.models import AsteriskSpec, ResolvedEndpoint

_env = Environment(
    loader=PackageLoader("kubevoip", "templates"),
    undefined=StrictUndefined,
    autoescape=False,
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_configs(
    spec: AsteriskSpec, endpoints: list[ResolvedEndpoint]
) -> dict[str, str]:
    values = {"spec": spec, "endpoints": endpoints}
    return {
        filename: _env.get_template(filename + ".j2").render(**values)
        for filename in ("pjsip.conf", "extensions.conf", "rtp.conf")
    }


def config_hash(configs: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for name in sorted(configs):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(configs[name].encode())
        digest.update(b"\0")
    return digest.hexdigest()

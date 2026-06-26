"""Render configuration for platform components."""

import hashlib
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from kubevoip.models import AsteriskPoolSpec, SIPGatewaySpec

TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATES = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=False,
    keep_trailing_newline=True,
    trim_blocks=False,
    lstrip_blocks=False,
    undefined=StrictUndefined,
)


def stable_hash(values: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def render_template(name: str, **values: object) -> str:
    return TEMPLATES.get_template(name).render(**values)


def render_worker_configs(spec: AsteriskPoolSpec) -> dict[str, str]:
    return {
        "pjsip.conf": render_template("asterisk/pjsip.conf.j2"),
        "extensions.conf": render_template("asterisk/extensions.conf.j2", echo_extension=spec.applications.echo_extension),
        "rtp.conf": render_template("asterisk/rtp.conf.j2"),
        "logger.conf": render_template("asterisk/logger.conf.j2"),
    }


def kamailio_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def kamailio_define(value: str) -> str:
    return kamailio_string(value)


def render_kamailio_config(
    spec: SIPGatewaySpec,
    gateway_name: str,
    namespace: str,
    external_address: str,
    internal_address: str,
    relay_endpoints: list[str],
) -> str:
    relay_sockets = " ".join(relay_endpoints)
    external_record_route = kamailio_string(external_address)
    internal_record_route = kamailio_string(internal_address)
    capture = spec.observability.capture
    capture_mode = {"transaction": "t", "dialog": "d"}[capture.capture_mode]
    if internal_address == external_address:
        record_route_line = "record_route();"
    else:
        record_route_line = (
            f'if (isflagset(1)) {{ record_route_preset("{internal_record_route}:5060;r2=on", "{external_record_route}:5060;r2=on"); }} '
            f'else {{ record_route_preset("{external_record_route}:5060;r2=on", "{internal_record_route}:5060;r2=on"); }}'
        )
    sql_namespace = namespace.replace("'", "''")
    sql_gateway = gateway_name.replace("'", "''")
    trusted_query_prefix = (
        "select t.name, t.inbound_dial_policy_name "
        "from kubevoip_sip_trunk t "
        "join kubevoip_sip_trunk_cidr c on c.namespace=t.namespace and c.trunk_name=t.name "
        f"where t.namespace='{sql_namespace}' and t.gateway_name='{sql_gateway}' "
        "and c.cidr >>= '"
    )
    trusted_query_suffix = (
        "'::inet "
        "order by t.name limit 1"
    )
    caller_query_prefix = (
        "select dial_policy_name from kubevoip_sip_user "
        f"where namespace='{sql_namespace}' and gateway_name='{sql_gateway}' "
        "and auth_username='"
    )
    caller_query_suffix = "' limit 1"
    route_query_prefix = (
        "select r.target_kind, r.target_ref, coalesce(r.target_extension,''), coalesce(r.target_host,''), "
        "coalesce(u.auth_username,''), coalesce(t.termination_uri,''), coalesce(t.outbound_caller_id,''), "
        "coalesce(t.digest_username,''), coalesce(t.digest_realm,''), coalesce(t.digest_ha1,'') "
        "from kubevoip_dial_policy_scope d "
        "join kubevoip_call_route r on r.namespace=d.namespace and r.scope_name=d.scope_name "
        "left join kubevoip_sip_user u on r.target_kind='SIPUser' and u.namespace=r.namespace and u.name=r.target_ref "
        "left join kubevoip_sip_trunk t on r.target_kind='SIPTrunk' and t.namespace=r.namespace and t.name=r.target_ref "
        f"where d.namespace='{sql_namespace}' and d.policy_name='"
    )
    route_query_middle = (
        "' "
        f"and r.gateway_name='{sql_gateway}' "
        "and (r.called_number='"
    )
    route_query_suffix = (
        "' or (right(r.called_number, 3)='...' "
        "and '"
    )
    route_query_end = (
        "' like left(r.called_number, length(r.called_number)-3) || '%')) "
        "order by d.position, r.priority, r.name limit 1"
    )
    return render_template(
        "kamailio.cfg.j2",
        external_address=external_address,
        internal_address=internal_address,
        auth_realm=gateway_name,
        relay_sockets=relay_sockets,
        namespace=kamailio_string(namespace),
        gateway_name=kamailio_string(gateway_name),
        capture=capture,
        sip_headers=spec.observability.sip_headers,
        sdp=spec.observability.sdp,
        capture_mode=capture_mode,
        hep_destination=f"sip:{kamailio_define(capture.hep_address)}:{capture.hep_port}",
        record_route_line=record_route_line,
        trusted_query_prefix=trusted_query_prefix,
        trusted_query_suffix=trusted_query_suffix,
        caller_query_prefix=caller_query_prefix,
        caller_query_suffix=caller_query_suffix,
        route_query_prefix=route_query_prefix,
        route_query_middle=route_query_middle,
        route_query_suffix=route_query_suffix,
        route_query_end=route_query_end,
    )

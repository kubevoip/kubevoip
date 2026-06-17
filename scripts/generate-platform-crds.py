#!/usr/bin/env python3
"""Generate structural CRDs for the experimental platform APIs."""

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
OUTPUTS = (
    ROOT / "config/crd/platform-crds.yaml",
    ROOT / "charts/kubevoip/crds/platform-crds.yaml",
)


def obj(properties, required=()):
    return {
        "type": "object",
        "properties": properties,
        **({"required": list(required)} if required else {}),
    }


def string(**kwargs):
    return {"type": "string", **kwargs}


def integer(**kwargs):
    return {"type": "integer", **kwargs}


def array(items, **kwargs):
    return {"type": "array", "items": items, **kwargs}


name = string(minLength=1)
address = string(minLength=1, maxLength=253)
local_ref = obj({"name": name}, ("name",))
secret_key_ref = obj({"name": name, "key": name}, ("name", "key"))
route_target = obj(
    {
        "sipUserRef": name,
        "asteriskPoolRef": name,
        "trunkRef": name,
        "extension": string(pattern=r"^[0-9]+$"),
    }
) | {
    "x-kubernetes-validations": [
        {
            "rule": "(has(self.sipUserRef) ? 1 : 0) + (has(self.asteriskPoolRef) ? 1 : 0) + (has(self.trunkRef) ? 1 : 0) == 1",
            "message": "exactly one route target is required",
        },
        {
            "rule": "!has(self.asteriskPoolRef) || has(self.extension)",
            "message": "Asterisk pool routes require extension",
        },
    ]
}
route_match = obj(
    {"calledNumber": string(pattern=r"^[+0-9.*]+$", maxLength=64)},
    ("calledNumber",),
)
service = obj(
    {
        "type": string(enum=["ClusterIP", "LoadBalancer"], default="ClusterIP"),
        "externalTrafficPolicy": string(enum=["Cluster", "Local"], default="Cluster"),
        "annotations": {"type": "object", "additionalProperties": string()},
    }
)
status = {"type": "object", "x-kubernetes-preserve-unknown-fields": True}

SPECS = {
    "NetworkProfile": obj(
        {
            "externalAddress": obj(
                {
                    "value": address,
                    "source": string(enum=["Service"]),
                },
                (),
            )
            | {"x-kubernetes-validations": [{"rule": "has(self.value) || has(self.source)", "message": "value or source is required"}]},
            "localNetworks": array(string()),
        },
        ("externalAddress",),
    ),
    "SIPUser": obj(
        {
            "gatewayRef": local_ref,
            "extension": string(pattern=r"^[0-9]+$", maxLength=20),
            "authUsername": string(pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$", maxLength=40),
            "callerId": string(maxLength=80),
            "passwordSecretRef": secret_key_ref,
        },
        ("gatewayRef", "extension", "authUsername", "passwordSecretRef"),
    ),
    "SIPTrunk": obj(
        {
            "gatewayRef": local_ref,
            "terminationUri": name,
            "inbound": obj({"allowedSourceCidrs": array(string())}),
            "outbound": obj(
                {
                    "callerIdSecretRef": secret_key_ref,
                    "authentication": obj(
                        {
                            "mode": string(enum=["None", "Digest"], default="None"),
                            "digest": obj(
                                {
                                    "usernameSecretRef": secret_key_ref,
                                    "passwordSecretRef": secret_key_ref,
                                    "realm": string(minLength=1, maxLength=253),
                                },
                                ("usernameSecretRef", "passwordSecretRef"),
                            ),
                        }
                    )
                    | {
                        "x-kubernetes-validations": [
                            {"rule": "self.mode != 'Digest' || has(self.digest)", "message": "Digest authentication requires digest settings"},
                            {"rule": "self.mode != 'None' || !has(self.digest)", "message": "digest settings require mode Digest"},
                        ]
                    },
                }
            ),
        },
        ("gatewayRef", "terminationUri"),
    ),
    "CallRoute": obj(
        {
            "gatewayRef": local_ref,
            "priority": integer(minimum=0, maximum=1000000, default=1000),
            "match": route_match,
            "target": route_target,
        },
        ("gatewayRef", "match", "target"),
    ),
    "MediaRelay": obj(
        {
            "replicas": integer(minimum=1, maximum=32, default=1),
            "image": name,
            "networkProfileRef": local_ref,
            "media": obj(
                {
                    "start": integer(minimum=1, maximum=65535),
                    "end": integer(minimum=1, maximum=65535),
                },
                ("start", "end"),
            )
            | {
                "x-kubernetes-validations": [
                    {"rule": "self.start <= self.end", "message": "start must not exceed end"},
                    {"rule": "self.end - self.start < 2000", "message": "media range cannot exceed 2000 ports"},
                ]
            },
            "network": obj(
                {
                    "mode": string(enum=["Service", "HostNetwork"], default="Service"),
                    "externalAddress": address,
                    "service": service,
                    "replicaOverrides": array(
                        obj(
                            {
                                "replica": integer(minimum=0),
                                "externalAddress": address,
                            },
                            ("replica", "externalAddress"),
                        ),
                        **{"x-kubernetes-list-type": "map", "x-kubernetes-list-map-keys": ["replica"]},
                    ),
                }
            ),
        },
        ("networkProfileRef", "media"),
    ),
    "AsteriskPool": obj(
        {
            "replicas": integer(minimum=1, maximum=32, default=1),
            "image": name,
            "applications": obj(
                {"echoExtension": string(pattern=r"^[0-9]+$", default="600")},
            ),
        }
    ),
    "SIPGateway": obj(
        {
            "replicas": integer(minimum=1, maximum=32, default=1),
            "image": name,
            "databaseSecretRef": local_ref,
            "networkProfileRef": local_ref,
            "mediaRelayRef": local_ref,
            "externalAddress": address,
            "internalAddress": address,
            "service": service,
        },
        ("databaseSecretRef", "networkProfileRef", "mediaRelayRef"),
    ),
}

PLURALS = {
    "NetworkProfile": ("networkprofiles", "networkprofile", ["netprofile"]),
    "SIPUser": ("sipusers", "sipuser", ["sipuser"]),
    "SIPTrunk": ("siptrunks", "siptrunk", ["siptrunk"]),
    "CallRoute": ("callroutes", "callroute", ["callroute"]),
    "MediaRelay": ("mediarelays", "mediarelay", ["relay"]),
    "AsteriskPool": ("asteriskpools", "asteriskpool", ["astpool"]),
    "SIPGateway": ("sipgateways", "sipgateway", ["sipgw"]),
}


def crd(kind):
    plural, singular, short_names = PLURALS[kind]
    return {
        "apiVersion": "apiextensions.k8s.io/v1",
        "kind": "CustomResourceDefinition",
        "metadata": {"name": f"{plural}.kubevoip.com"},
        "spec": {
            "group": "kubevoip.com",
            "scope": "Namespaced",
            "names": {
                "plural": plural,
                "singular": singular,
                "kind": kind,
                "shortNames": short_names,
            },
            "versions": [
                {
                    "name": "v1alpha1",
                    "served": True,
                    "storage": True,
                    "subresources": {"status": {}},
                    "additionalPrinterColumns": [
                        {"name": "Phase", "type": "string", "jsonPath": ".status.phase"},
                    ],
                    "schema": {
                        "openAPIV3Schema": obj(
                            {"spec": SPECS[kind], "status": status},
                            ("spec",),
                        )
                    },
                }
            ],
        },
    }


rendered = yaml.safe_dump_all(
    [crd(kind) for kind in PLURALS],
    explicit_start=True,
    sort_keys=False,
)
for output in OUTPUTS:
    output.write_text(rendered)

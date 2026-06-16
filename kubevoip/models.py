"""Validated custom-resource models."""

import ipaddress
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from kubevoip.config import (
    DEFAULT_ASTERISK_IMAGE,
    DEFAULT_ASTERISK_WORKER_IMAGE,
    DEFAULT_KAMAILIO_IMAGE,
    DEFAULT_RTPENGINE_IMAGE,
    MAX_PLATFORM_RTP_PORTS,
    MAX_RTP_PORTS,
)


class Model(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


def validate_external_address(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        if len(value) > 253 or not re.fullmatch(
            r"(?=.{1,253}\.?$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.?",
            value,
        ):
            raise ValueError("external address must be an IP address or hostname") from None
        return value


class SecretKeyRef(Model):
    name: str = Field(min_length=1)
    key: str = Field(min_length=1)


class LocalReference(Model):
    name: str = Field(min_length=1)


class Endpoint(Model):
    name: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$", max_length=40)
    extension: str = Field(pattern=r"^[0-9]+$", max_length=20)
    password_secret_ref: SecretKeyRef = Field(alias="passwordSecretRef")
    caller_id: str | None = Field(default=None, alias="callerId", max_length=80)


class ServiceSpec(Model):
    type: Literal["ClusterIP", "NodePort", "LoadBalancer"] = "ClusterIP"
    external_traffic_policy: Literal["Cluster", "Local"] = Field(default="Cluster", alias="externalTrafficPolicy")
    annotations: dict[str, str] = Field(default_factory=dict)


class SipSpec(Model):
    port: int = Field(default=5060, ge=1, le=65535)


class RtpSpec(Model):
    start: int = Field(default=10000, ge=1, le=65535)
    end: int = Field(default=10100, ge=1, le=65535)

    @model_validator(mode="after")
    def validate_range(self) -> "RtpSpec":
        if self.start > self.end:
            raise ValueError("rtp.start must be less than or equal to rtp.end")
        if self.end - self.start + 1 > MAX_RTP_PORTS:
            raise ValueError(f"RTP range cannot exceed {MAX_RTP_PORTS} ports")
        return self


class DialplanSpec(Model):
    echo_extension: str = Field(default="600", alias="echoExtension", pattern=r"^[0-9]+$")


class AsteriskSpec(Model):
    image: str = Field(default=DEFAULT_ASTERISK_IMAGE, min_length=1)
    service: ServiceSpec = Field(default_factory=ServiceSpec)
    sip: SipSpec = Field(default_factory=SipSpec)
    rtp: RtpSpec = Field(default_factory=RtpSpec)
    endpoints: list[Endpoint] = Field(default_factory=list)
    dialplan: DialplanSpec = Field(default_factory=DialplanSpec)

    @model_validator(mode="after")
    def validate_unique_values(self) -> "AsteriskSpec":
        names = [item.name for item in self.endpoints]
        extensions = [item.extension for item in self.endpoints]
        if len(names) != len(set(names)):
            raise ValueError("endpoint names must be unique")
        if len(extensions) != len(set(extensions)):
            raise ValueError("endpoint extensions must be unique")
        if self.dialplan.echo_extension in extensions:
            raise ValueError("echo extension must not conflict with an endpoint extension")
        return self


class ResolvedEndpoint(Model):
    name: str
    extension: str
    password: str
    caller_id: str


class ExternalAddressSpec(Model):
    value: str | None = Field(default=None, min_length=1)
    source: Literal["Service"] | None = None

    _validate_value = field_validator("value")(validate_external_address)

    @model_validator(mode="after")
    def validate_source(self) -> "ExternalAddressSpec":
        if not self.value and not self.source:
            raise ValueError("externalAddress requires value or source")
        return self


class NetworkProfileSpec(Model):
    external_address: ExternalAddressSpec = Field(alias="externalAddress")
    local_networks: list[str] = Field(default_factory=list, alias="localNetworks")

    @model_validator(mode="after")
    def validate_networks(self) -> "NetworkProfileSpec":
        for network in self.local_networks:
            ipaddress.ip_network(network, strict=False)
        return self


class MediaRange(Model):
    start: int = Field(ge=1, le=65535)
    end: int = Field(ge=1, le=65535)

    @model_validator(mode="after")
    def validate_range(self) -> "MediaRange":
        if self.start > self.end:
            raise ValueError("media.start must be less than or equal to media.end")
        if self.end - self.start + 1 > MAX_PLATFORM_RTP_PORTS:
            raise ValueError(f"media range cannot exceed {MAX_PLATFORM_RTP_PORTS} ports")
        return self


class ReplicaOverride(Model):
    replica: int = Field(ge=0)
    external_address: str = Field(alias="externalAddress", min_length=1)

    _validate_address = field_validator("external_address")(validate_external_address)


class MediaRelayNetwork(Model):
    mode: Literal["Service", "HostNetwork"] = "Service"
    external_address: str | None = Field(default=None, alias="externalAddress", min_length=1)
    service: ServiceSpec = Field(default_factory=ServiceSpec)
    replica_overrides: list[ReplicaOverride] = Field(default_factory=list, alias="replicaOverrides")

    _validate_address = field_validator("external_address")(validate_external_address)


class MediaRelaySpec(Model):
    replicas: int = Field(default=1, ge=1, le=32)
    image: str = Field(default=DEFAULT_RTPENGINE_IMAGE, min_length=1)
    network_profile_ref: LocalReference = Field(alias="networkProfileRef")
    media: MediaRange
    network: MediaRelayNetwork = Field(default_factory=MediaRelayNetwork)

    @model_validator(mode="after")
    def validate_replicas(self) -> "MediaRelaySpec":
        ports = self.media.end - self.media.start + 1
        if ports < self.replicas:
            raise ValueError("media range must contain at least one port per replica")
        indexes = [item.replica for item in self.network.replica_overrides]
        if len(indexes) != len(set(indexes)) or any(index_ >= self.replicas for index_ in indexes):
            raise ValueError("replica overrides must be unique and reference an existing replica")
        if self.network.service.type == "NodePort":
            raise ValueError("MediaRelay supports only ClusterIP and LoadBalancer Services")
        return self


class ApplicationsSpec(Model):
    echo_extension: str = Field(default="600", alias="echoExtension", pattern=r"^[0-9]+$")


class AsteriskPoolSpec(Model):
    replicas: int = Field(default=1, ge=1, le=32)
    image: str = Field(default=DEFAULT_ASTERISK_WORKER_IMAGE, min_length=1)
    applications: ApplicationsSpec = Field(default_factory=ApplicationsSpec)


class SIPUserSpec(Model):
    gateway_ref: LocalReference = Field(alias="gatewayRef")
    extension: str = Field(pattern=r"^[0-9]+$", max_length=20)
    auth_username: str = Field(alias="authUsername", pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$", max_length=40)
    caller_id: str | None = Field(default=None, alias="callerId", max_length=80)
    password_secret_ref: SecretKeyRef = Field(alias="passwordSecretRef")


class DatabaseSecretRef(Model):
    name: str = Field(min_length=1)


class TrunkAuthentication(Model):
    mode: Literal["IP"] = "IP"


class TrunkSpec(Model):
    name: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$", max_length=40)
    termination_uri: str = Field(alias="terminationUri", min_length=1)
    authentication: TrunkAuthentication = Field(default_factory=TrunkAuthentication)
    allowed_source_cidrs: list[str] = Field(default_factory=list, alias="allowedSourceCidrs")

    @model_validator(mode="after")
    def validate_cidrs(self) -> "TrunkSpec":
        for network in self.allowed_source_cidrs:
            ipaddress.ip_network(network, strict=False)
        return self


class RouteMatch(Model):
    called_number: str = Field(alias="calledNumber", pattern=r"^[+0-9.*]+$", max_length=64)


class RouteTarget(Model):
    sip_user_ref: str | None = Field(default=None, alias="sipUserRef")
    asterisk_pool_ref: str | None = Field(default=None, alias="asteriskPoolRef")
    trunk_ref: str | None = Field(default=None, alias="trunkRef")
    extension: str | None = Field(default=None, pattern=r"^[0-9]+$")

    @model_validator(mode="after")
    def validate_target(self) -> "RouteTarget":
        if sum(bool(value) for value in (self.sip_user_ref, self.asterisk_pool_ref, self.trunk_ref)) != 1:
            raise ValueError("route target requires exactly one of sipUserRef, asteriskPoolRef, or trunkRef")
        if self.asterisk_pool_ref and not self.extension:
            raise ValueError("Asterisk pool route requires extension")
        return self


class RouteSpec(Model):
    match: RouteMatch
    target: RouteTarget


class SIPGatewaySpec(Model):
    replicas: int = Field(default=1, ge=1, le=32)
    image: str = Field(default=DEFAULT_KAMAILIO_IMAGE, min_length=1)
    database_secret_ref: DatabaseSecretRef = Field(alias="databaseSecretRef")
    network_profile_ref: LocalReference = Field(alias="networkProfileRef")
    media_relay_ref: LocalReference = Field(alias="mediaRelayRef")
    external_address: str | None = Field(default=None, alias="externalAddress", min_length=1)
    internal_address: str | None = Field(default=None, alias="internalAddress", min_length=1)
    service: ServiceSpec = Field(default_factory=ServiceSpec)
    trunks: list[TrunkSpec] = Field(default_factory=list)
    routes: list[RouteSpec] = Field(default_factory=list)

    _validate_address = field_validator("external_address")(validate_external_address)
    _validate_internal_address = field_validator("internal_address")(validate_external_address)

    @model_validator(mode="after")
    def validate_service(self) -> "SIPGatewaySpec":
        if self.service.type == "NodePort":
            raise ValueError("SIPGateway supports only ClusterIP and LoadBalancer Services")
        trunk_names = [trunk.name for trunk in self.trunks]
        if len(trunk_names) != len(set(trunk_names)):
            raise ValueError("trunk names must be unique")
        known_trunks = set(trunk_names)
        if any(route.target.trunk_ref not in known_trunks for route in self.routes if route.target.trunk_ref):
            raise ValueError("route target references an unknown trunk")
        return self

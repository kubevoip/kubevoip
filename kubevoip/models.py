"""Validated custom-resource models."""

import ipaddress
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from kubevoip.config import (
    DEFAULT_ASTERISK_WORKER_IMAGE,
    DEFAULT_KAMAILIO_IMAGE,
    DEFAULT_RTPENGINE_IMAGE,
    MAX_PLATFORM_RTP_PORTS,
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


class ServiceSpec(Model):
    type: Literal["ClusterIP", "NodePort", "LoadBalancer"] = "ClusterIP"
    external_traffic_policy: Literal["Cluster", "Local"] = Field(default="Cluster", alias="externalTrafficPolicy")
    annotations: dict[str, str] = Field(default_factory=dict)


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
    dial_policy_ref: LocalReference = Field(alias="dialPolicyRef")
    extension: str = Field(pattern=r"^[0-9]+$", max_length=20)
    auth_username: str = Field(alias="authUsername", pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$", max_length=40)
    caller_id: str | None = Field(default=None, alias="callerId", max_length=80)
    password_secret_ref: SecretKeyRef = Field(alias="passwordSecretRef")


class DatabaseSecretRef(Model):
    name: str = Field(min_length=1)


class HomerCaptureSpec(Model):
    enabled: bool = False
    type: Literal["Homer"] = "Homer"
    hep_address: str = Field(default="homer-heplify.telemetry.svc.cluster.local", alias="hepAddress", min_length=1, max_length=253)
    hep_port: int = Field(default=9060, alias="hepPort", ge=1, le=65535)
    hep_transport: Literal["udp"] = Field(default="udp", alias="hepTransport")
    capture_mode: Literal["transaction", "dialog"] = Field(default="transaction", alias="captureMode")
    include_payload: bool = Field(default=True, alias="includePayload")

    _validate_hep_address = field_validator("hep_address")(validate_external_address)

    @model_validator(mode="after")
    def validate_payload(self) -> "HomerCaptureSpec":
        if self.enabled and not self.include_payload:
            raise ValueError("HOMER capture requires includePayload=true")
        return self


class ObservabilitySpec(Model):
    capture: HomerCaptureSpec = Field(default_factory=HomerCaptureSpec)


class DigestAuthentication(Model):
    username_secret_ref: SecretKeyRef = Field(alias="usernameSecretRef")
    password_secret_ref: SecretKeyRef = Field(alias="passwordSecretRef")
    realm: str | None = Field(default=None, min_length=1, max_length=253)


class TrunkOutboundAuthentication(Model):
    mode: Literal["None", "Digest"] = "None"
    digest: DigestAuthentication | None = None

    @model_validator(mode="after")
    def validate_digest(self) -> "TrunkOutboundAuthentication":
        if self.mode == "Digest" and not self.digest:
            raise ValueError("Digest authentication requires digest settings")
        if self.mode == "Digest" and self.digest and not self.digest.realm:
            raise ValueError("Digest authentication requires digest.realm")
        if self.mode == "None" and self.digest:
            raise ValueError("digest settings require mode Digest")
        return self


class TrunkInboundSpec(Model):
    allowed_source_cidrs: list[str] = Field(default_factory=list, alias="allowedSourceCidrs")
    dial_policy_ref: LocalReference | None = Field(default=None, alias="dialPolicyRef")

    @model_validator(mode="after")
    def validate_cidrs(self) -> "TrunkInboundSpec":
        for network in self.allowed_source_cidrs:
            ipaddress.ip_network(network, strict=False)
        if self.allowed_source_cidrs and not self.dial_policy_ref:
            raise ValueError("trusted inbound trunks require inbound.dialPolicyRef")
        return self


class TrunkOutboundSpec(Model):
    caller_id_secret_ref: SecretKeyRef | None = Field(default=None, alias="callerIdSecretRef")
    authentication: TrunkOutboundAuthentication = Field(default_factory=TrunkOutboundAuthentication)


class SIPTrunkSpec(Model):
    gateway_ref: LocalReference = Field(alias="gatewayRef")
    termination_uri: str = Field(alias="terminationUri", min_length=1)
    inbound: TrunkInboundSpec = Field(default_factory=TrunkInboundSpec)
    outbound: TrunkOutboundSpec = Field(default_factory=TrunkOutboundSpec)


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


class CallRouteSpec(Model):
    gateway_ref: LocalReference = Field(alias="gatewayRef")
    scope_ref: LocalReference = Field(alias="scopeRef")
    priority: int = Field(default=1000, ge=0, le=1_000_000)
    match: RouteMatch
    target: RouteTarget


class CallScopeSpec(Model):
    gateway_ref: LocalReference = Field(alias="gatewayRef")


class DialPolicySpec(Model):
    gateway_ref: LocalReference = Field(alias="gatewayRef")
    scopes: list[LocalReference] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_scopes(self) -> "DialPolicySpec":
        names = [item.name for item in self.scopes]
        if len(names) != len(set(names)):
            raise ValueError("DialPolicy scopes must be unique")
        return self


class SIPGatewaySpec(Model):
    replicas: int = Field(default=1, ge=1, le=32)
    image: str = Field(default=DEFAULT_KAMAILIO_IMAGE, min_length=1)
    database_secret_ref: DatabaseSecretRef = Field(alias="databaseSecretRef")
    network_profile_ref: LocalReference = Field(alias="networkProfileRef")
    media_relay_ref: LocalReference = Field(alias="mediaRelayRef")
    external_address: str | None = Field(default=None, alias="externalAddress", min_length=1)
    internal_address: str | None = Field(default=None, alias="internalAddress", min_length=1)
    service: ServiceSpec = Field(default_factory=ServiceSpec)
    observability: ObservabilitySpec = Field(default_factory=ObservabilitySpec)

    _validate_address = field_validator("external_address")(validate_external_address)
    _validate_internal_address = field_validator("internal_address")(validate_external_address)

    @model_validator(mode="after")
    def validate_service(self) -> "SIPGatewaySpec":
        if self.service.type == "NodePort":
            raise ValueError("SIPGateway supports only ClusterIP and LoadBalancer Services")
        return self

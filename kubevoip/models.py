"""Validated custom-resource models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kubevoip.config import DEFAULT_ASTERISK_IMAGE, MAX_RTP_PORTS


class Model(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class SecretKeyRef(Model):
    name: str = Field(min_length=1)
    key: str = Field(min_length=1)


class Endpoint(Model):
    name: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$", max_length=40)
    extension: str = Field(pattern=r"^[0-9]+$", max_length=20)
    password_secret_ref: SecretKeyRef = Field(alias="passwordSecretRef")
    caller_id: str | None = Field(default=None, alias="callerId", max_length=80)


class ServiceSpec(Model):
    type: Literal["ClusterIP", "NodePort", "LoadBalancer"] = "ClusterIP"


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

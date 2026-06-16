"""Operator-wide defaults."""

import os

GROUP = "kubevoip.com"
VERSION = "v1alpha1"
PLURAL = "asterisks"
FIELD_MANAGER = "kubevoip"
DEFAULT_ASTERISK_IMAGE = os.getenv(
    "KUBEVOIP_ASTERISK_IMAGE", "ghcr.io/danohn/kubevoip-asterisk:v0.2.4"
)
DEFAULT_ASTERISK_WORKER_IMAGE = os.getenv(
    "KUBEVOIP_ASTERISK_WORKER_IMAGE", "ghcr.io/danohn/kubevoip-asterisk-worker:v0.2.4"
)
DEFAULT_KAMAILIO_IMAGE = os.getenv(
    "KUBEVOIP_KAMAILIO_IMAGE", "ghcr.io/danohn/kubevoip-kamailio:v0.2.4"
)
DEFAULT_RTPENGINE_IMAGE = os.getenv(
    "KUBEVOIP_RTPENGINE_IMAGE", "ghcr.io/danohn/kubevoip-rtpengine:v0.2.4"
)
MAX_RTP_PORTS = 200
MAX_PLATFORM_RTP_PORTS = 2000

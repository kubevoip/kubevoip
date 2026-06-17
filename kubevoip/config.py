"""Operator-wide defaults."""

import os

GROUP = "kubevoip.com"
VERSION = "v1alpha1"
FIELD_MANAGER = "kubevoip"
DEFAULT_ASTERISK_WORKER_IMAGE = os.getenv(
    "KUBEVOIP_ASTERISK_WORKER_IMAGE", "ghcr.io/kubevoip/kubevoip-asterisk-worker:v0.4.1"
)
DEFAULT_KAMAILIO_IMAGE = os.getenv(
    "KUBEVOIP_KAMAILIO_IMAGE", "ghcr.io/kubevoip/kubevoip-kamailio:v0.4.1"
)
DEFAULT_RTPENGINE_IMAGE = os.getenv(
    "KUBEVOIP_RTPENGINE_IMAGE", "ghcr.io/kubevoip/kubevoip-rtpengine:v0.4.1"
)
MAX_PLATFORM_RTP_PORTS = 2000

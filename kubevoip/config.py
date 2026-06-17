"""Operator-wide defaults."""

import os

GROUP = "kubevoip.com"
VERSION = "v1alpha1"
FIELD_MANAGER = "kubevoip"
DEFAULT_ASTERISK_WORKER_IMAGE = os.getenv(
    "KUBEVOIP_ASTERISK_IMAGE",
    os.getenv("KUBEVOIP_ASTERISK_WORKER_IMAGE", "ghcr.io/kubevoip/kubevoip-asterisk:v0.4.3"),
)
DEFAULT_KAMAILIO_IMAGE = os.getenv(
    "KUBEVOIP_KAMAILIO_IMAGE", "ghcr.io/kubevoip/kubevoip-kamailio:v0.4.3"
)
DEFAULT_RTPENGINE_IMAGE = os.getenv(
    "KUBEVOIP_RTPENGINE_IMAGE", "ghcr.io/kubevoip/kubevoip-rtpengine:v0.4.3"
)
MAX_PLATFORM_RTP_PORTS = 2000

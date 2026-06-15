FROM debian:bookworm-slim
ARG KAMAILIO_VERSION=5.6.3-2
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates kamailio="${KAMAILIO_VERSION}" kamailio-extra-modules="${KAMAILIO_VERSION}" \
    kamailio-postgres-modules="${KAMAILIO_VERSION}" procps python3-minimal tini \
 && rm -rf /var/lib/apt/lists/*
COPY runtime/kamailio/entrypoint.sh /usr/local/bin/kubevoip-kamailio
RUN chmod 0755 /usr/local/bin/kubevoip-kamailio \
 && useradd --system --uid 10001 --home /run/kamailio kamailio-kubevoip \
 && mkdir -p /run/kamailio /work \
 && chown -R kamailio-kubevoip:kamailio-kubevoip /run/kamailio /work
USER 10001
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/kubevoip-kamailio"]

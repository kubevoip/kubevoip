FROM debian:bookworm-slim AS builder
ARG ASTERISK_VERSION=22.10.0
ARG ASTERISK_SHA256=27e49d483efb0739faf7d0a17a9e55f88439347ed9668f24eea909440473c32e
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl libedit-dev libjansson-dev libsqlite3-dev \
    libssl-dev libxml2-dev libxslt1-dev pkg-config uuid-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN curl -fsSLO "https://downloads.asterisk.org/pub/telephony/asterisk/releases/asterisk-${ASTERISK_VERSION}.tar.gz" \
 && echo "${ASTERISK_SHA256}  asterisk-${ASTERISK_VERSION}.tar.gz" | sha256sum -c - \
 && tar -xzf "asterisk-${ASTERISK_VERSION}.tar.gz"
WORKDIR /src/asterisk-${ASTERISK_VERSION}
RUN ./configure --prefix=/usr --sysconfdir=/etc --localstatedir=/var --with-pjproject-bundled \
 && make menuselect.makeopts \
 && menuselect/menuselect --disable-all \
    --enable app_dial --enable app_echo --enable chan_pjsip --enable codec_ulaw --enable format_pcm \
    --enable pbx_config --enable res_geolocation --enable res_pjproject --enable res_pjsip --enable res_pjsip_authenticator_digest \
    --enable res_pjsip_endpoint_identifier_ip --enable res_pjsip_endpoint_identifier_user --enable res_pjsip_mwi --enable res_pjsip_outbound_publish \
    --enable res_pjsip_pubsub --enable res_pjsip_registrar --enable res_pjsip_sdp_rtp --enable res_rtp_asterisk --enable res_statsd menuselect.makeopts \
 && make -j"$(nproc)" && make DESTDIR=/out install

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libedit2 libjansson4 libsqlite3-0 libssl3 libxml2 libxslt1.1 libuuid1 tini \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --gid 1000 asterisk && useradd --uid 1000 --gid 1000 --home-dir /var/lib/asterisk asterisk
COPY --from=builder /out/usr/ /usr/
COPY --from=builder /out/var/lib/asterisk/ /var/lib/asterisk/
COPY runtime/*.conf /etc/asterisk/
RUN mkdir -p /var/lib/asterisk /var/log/asterisk /var/run/asterisk /var/spool/asterisk \
 && chown -R asterisk:asterisk /etc/asterisk /var/lib/asterisk /var/log/asterisk /var/run/asterisk /var/spool/asterisk
USER 1000:1000
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["asterisk", "-f"]

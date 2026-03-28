FROM docker.io/metacubex/mihomo:latest

WORKDIR /tmp/openclash

ARG OPENCLASH_BUILD_ALPINE_REPO=https://dl-cdn.alpinelinux.org/alpine
ARG OPENCLASH_BUILD_METACUBEXD_URL=https://codeload.github.com/MetaCubeX/metacubexd/tar.gz/gh-pages

RUN apk add --no-cache \
    --repository "${OPENCLASH_BUILD_ALPINE_REPO}/v3.22/main" \
    --repository "${OPENCLASH_BUILD_ALPINE_REPO}/v3.22/community" \
    ca-certificates \
    curl \
    rsync \
    python3 \
    py3-yaml \
    tar \
  && curl -fsSL "${OPENCLASH_BUILD_METACUBEXD_URL}" -o /tmp/metacubexd.tar.gz \
  && mkdir -p /opt/metacubexd \
  && tar -xzf /tmp/metacubexd.tar.gz -C /opt/metacubexd --strip-components=1 \
  && rm -f /tmp/metacubexd.tar.gz

COPY scripts/bootstrap-openclash.sh /usr/local/bin/bootstrap-openclash.sh
COPY scripts/render_openclash_config.py /usr/local/bin/render_openclash_config.py

RUN chmod +x /usr/local/bin/bootstrap-openclash.sh

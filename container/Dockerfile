# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

# Blender publishes an official Linux x64 archive, not an official OCI image.
# Both stages pin the same Ubuntu 24.04 OCI index and dated Ubuntu archive
# snapshot. Build with --platform linux/amd64.
ARG SOURCE_DATE_EPOCH=1785542400
FROM --platform=linux/amd64 ubuntu:24.04@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90 AS fetch

ARG BLENDER_VERSION=4.5.12
ARG BLENDER_ARCHIVE_SHA256=95e3a2dfedba3bd32ca54fc355eac6b15a11986954ccb02815a07535d0120a25
ARG UBUNTU_SNAPSHOT=20260731T000000Z

COPY container/ubuntu.sources /etc/apt/sources.list.d/ubuntu.sources
COPY container/ubuntu-bootstrap.lock container/ubuntu-fetch.lock /tmp/neuralstock-locks/

# ubuntu:24.04 intentionally omits a CA bundle. Bootstrap it from the signed,
# dated Ubuntu snapshot, then discard the indexes and require verified TLS for
# every subsequent APT request and for the Blender archive download.
RUN set -eux; \
    grep --fixed-strings --line-regexp \
      "URIs: https://snapshot.ubuntu.com/ubuntu/${UBUNTU_SNAPSHOT}" \
      /etc/apt/sources.list.d/ubuntu.sources; \
    apt-get -o Acquire::https::Verify-Peer=false update; \
    DEBIAN_FRONTEND=noninteractive \
      xargs --no-run-if-empty apt-get -o Acquire::https::Verify-Peer=false \
        install --yes --no-install-recommends \
        < /tmp/neuralstock-locks/ubuntu-bootstrap.lock; \
    rm -rf /var/lib/apt/lists/*; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive \
      xargs --no-run-if-empty apt-get install --yes --no-install-recommends \
        < /tmp/neuralstock-locks/ubuntu-fetch.lock; \
    for lock in /tmp/neuralstock-locks/*.lock; do \
      while IFS='=' read -r package expected; do \
        actual="$(dpkg-query --show --showformat='${Version}' "$package")"; \
        test "$actual" = "$expected"; \
      done < "$lock"; \
    done; \
    rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    archive="blender-${BLENDER_VERSION}-linux-x64.tar.xz"; \
    curl --fail --location --proto '=https' --tlsv1.2 \
      "https://download.blender.org/release/Blender4.5/${archive}" \
      --output "/tmp/${archive}"; \
    echo "${BLENDER_ARCHIVE_SHA256}  /tmp/${archive}" | sha256sum --check --strict; \
    mkdir -p /opt/blender; \
    tar --extract --xz --file "/tmp/${archive}" --directory /opt/blender --strip-components=1; \
    rm "/tmp/${archive}"

FROM --platform=linux/amd64 ubuntu:24.04@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90

ARG BLENDER_VERSION=4.5.12
ARG BLENDER_ARCHIVE_SHA256=95e3a2dfedba3bd32ca54fc355eac6b15a11986954ccb02815a07535d0120a25
ARG BLENDER_SOURCE_SHA256=9cb86825c95e4f0a33bfd41eb574426f2f69aa6c310497e289fdb54cc6482f1b
ARG UBUNTU_SNAPSHOT=20260731T000000Z

LABEL org.opencontainers.image.title="NeuralStock Blender Worker" \
      org.opencontainers.image.description="Pinned, headless Blender runner for NeuralStock asset ingestion" \
      org.opencontainers.image.version="${BLENDER_VERSION}" \
      org.opencontainers.image.licenses="MIT AND GPL-2.0-or-later AND LicenseRef-Blender-Third-Party AND LicenseRef-Ubuntu-Runtime-Packages" \
      org.opencontainers.image.source="https://github.com/Neuralstock/neuralstock" \
      org.opencontainers.image.documentation="https://github.com/Neuralstock/neuralstock/blob/main/container/THIRD_PARTY_NOTICES.md" \
      org.opencontainers.image.base.name="docker.io/library/ubuntu:24.04" \
      org.opencontainers.image.base.digest="sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90" \
      org.neuralstock.blender.archive.sha256="${BLENDER_ARCHIVE_SHA256}" \
      org.neuralstock.blender.source.sha256="${BLENDER_SOURCE_SHA256}" \
      org.neuralstock.licenses.path="/usr/share/neuralstock/licenses/THIRD_PARTY_NOTICES.md" \
      org.neuralstock.ubuntu.snapshot="${UBUNTU_SNAPSHOT}"

COPY --from=fetch /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
COPY --from=fetch /usr/share/doc/ca-certificates/copyright /usr/share/doc/ca-certificates/copyright
COPY container/ubuntu.sources /etc/apt/sources.list.d/ubuntu.sources
COPY container/ubuntu-runtime.lock /tmp/neuralstock-locks/ubuntu-runtime.lock

RUN set -eux; \
    grep --fixed-strings --line-regexp \
      "URIs: https://snapshot.ubuntu.com/ubuntu/${UBUNTU_SNAPSHOT}" \
      /etc/apt/sources.list.d/ubuntu.sources; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive \
      xargs --no-run-if-empty apt-get install --yes --no-install-recommends \
        < /tmp/neuralstock-locks/ubuntu-runtime.lock; \
    while IFS='=' read -r package expected; do \
      actual="$(dpkg-query --show --showformat='${Version}' "$package")"; \
      test "$actual" = "$expected"; \
    done < /tmp/neuralstock-locks/ubuntu-runtime.lock; \
    rm -rf /var/lib/apt/lists/*; \
    groupadd --gid 65532 neuralstock; \
    useradd --uid 65532 --gid 65532 --home-dir /tmp/neuralstock-home \
      --no-create-home --shell /usr/sbin/nologin neuralstock; \
    rm -f \
      /var/cache/ldconfig/aux-cache \
      /var/log/alternatives.log \
      /var/log/apt/history.log \
      /var/log/apt/term.log \
      /var/log/dpkg.log

COPY --from=fetch /opt/blender /opt/blender
COPY blender /opt/neuralstock/blender
COPY container/entrypoint.sh /usr/local/bin/neuralstock-blender
COPY container/ubuntu.sources container/ubuntu-*.lock /usr/share/neuralstock/container-locks/
COPY LICENSE /usr/share/neuralstock/licenses/neuralstock-MIT.txt
COPY container/THIRD_PARTY_NOTICES.md /usr/share/neuralstock/licenses/THIRD_PARTY_NOTICES.md

RUN chmod 0555 /usr/local/bin/neuralstock-blender \
    && find /opt/neuralstock/blender -type f -name '*.py' -exec chmod 0444 {} + \
    && test -f /opt/blender/copyright.txt \
    && test -f /opt/blender/license/license.md \
    && test -f /opt/blender/license/licenses.json \
    && test -f /usr/share/neuralstock/licenses/neuralstock-MIT.txt \
    && test -f /usr/share/neuralstock/licenses/THIRD_PARTY_NOTICES.md \
    && test -f /usr/share/doc/ca-certificates/copyright

ENV PATH="/opt/blender:${PATH}" \
    BLENDER_SYSTEM_SCRIPTS="/opt/blender/4.5/scripts" \
    NEURALSTOCK_CONTAINER_HOME="/tmp/neuralstock-home" \
    LIBGL_ALWAYS_SOFTWARE="1" \
    PYTHONNOUSERSITE="1" \
    PYTHONPATH="/opt/neuralstock/blender"

USER neuralstock:neuralstock
WORKDIR /work
ENTRYPOINT ["/usr/local/bin/neuralstock-blender"]
CMD ["help"]

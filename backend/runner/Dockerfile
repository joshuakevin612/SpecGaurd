FROM python:3.11-slim@sha256:b7a9e5f6a93d6d4a31f129bbd4bdee69efccb6ded0fb230d78aafaf37af98377
RUN python -m pip uninstall --yes pip setuptools wheel \
    && useradd --uid 10001 --create-home runner
USER runner
WORKDIR /work

FROM ghcr.io/astral-sh/uv:0.7.13 AS uv

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml README.md /app/
COPY kubevoip /app/kubevoip
COPY database /app/database
RUN uv pip install --system --no-cache . \
 && find /app -type d -name __pycache__ -prune -exec rm -rf {} +
RUN groupadd --gid 65532 kubevoip \
 && useradd --uid 65532 --gid 65532 --no-create-home --shell /usr/sbin/nologin kubevoip \
 && chmod -R a+rX /app
USER 65532:65532
ENTRYPOINT ["kopf", "run", "/app/kubevoip/main.py"]

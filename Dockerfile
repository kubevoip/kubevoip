FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY pyproject.toml README.md /app/
COPY kubevoip /app/kubevoip
RUN pip install --no-cache-dir .
RUN groupadd --gid 65532 kubevoip \
 && useradd --uid 65532 --gid 65532 --no-create-home --shell /usr/sbin/nologin kubevoip \
 && chmod -R a+rX /app
USER 65532:65532
ENTRYPOINT ["kopf", "run", "/app/kubevoip/main.py", "--all-namespaces"]

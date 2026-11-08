FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --gid 5005 pythongroup && \
    useradd --uid 5060 --gid pythongroup --home /app pythonuser && \
    mkdir -p /app/instance && chown -R pythonuser:pythongroup /app

WORKDIR /app

# Install dependencies first so this layer is cached between code changes
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=pythonuser:pythongroup . .

USER pythonuser

EXPOSE 8000

CMD ["gunicorn", "-b", "0.0.0.0:8000", "--statsd-host=statsd-exporter-service:9125", "--statsd-prefix=tml_nft_bot", "-w", "2", "--timeout", "10", "--preload", "app:app"]

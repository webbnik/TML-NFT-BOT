FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --gid 5005 pythongroup && \
    useradd --uid 5060 --gid pythongroup --home /app pythonuser && \
    mkdir -p /app/instance /app/backups && chown -R pythonuser:pythongroup /app

WORKDIR /app

# Install dependencies first so this layer is cached between code changes
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=pythonuser:pythongroup . .


# Tests: docker build --target test .   (the build fails if a test fails)
FROM base AS test
RUN pip install -r requirements-dev.txt
USER pythonuser
RUN TML_DISABLE_SCHEDULER=1 python -m pytest -q -p no:cacheprovider


FROM base AS production
USER pythonuser
EXPOSE 8000
CMD ["gunicorn", "-b", "0.0.0.0:8000", "-w", "2", "--timeout", "10", "--preload", "app:app"]

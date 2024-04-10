# syntax=docker/dockerfile:1

FROM python:3.10-slim-bullseye

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1
# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1
# The home directory for this app. This will be volume mounted in docker-compose.yml
# and will also contain the config file
ENV CLOCKIFY_INVOICE_HOME=/invoices
# Optionally set the API key here or in the config file
# Config file is preferred
ENV CLOCKIFY_API_KEY=

# Install weasyprint
# https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#debian-11
RUN : \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive \
    apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
    && apt-get -y clean \
    && rm -rf /var/lib/apt/lists/*

# Create a non-privileged user that the app will run under.
# See https://docs.docker.com/develop/develop-images/dockerfile_best-practices/#user
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --shell "/sbin/nologin" \
    --uid "${UID}" \
    appuser

WORKDIR /app

# Copy the source code into the container.
COPY clockify_invoice clockify_invoice
COPY setup.py .
COPY setup.cfg .
COPY README.md .

RUN python -m pip install . --no-cache-dir

# Switch to the non-privileged user to run the application.
USER appuser

# Run the application.
CMD ["clockify-invoice", "-v", "--synch",  "-i"]

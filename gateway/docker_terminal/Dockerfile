FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --timeout 120 \
    open-terminal \
    requests \
    beautifulsoup4 \
    lxml \
    cssselect \
    pandas

# Working directory for Kitty scripts
WORKDIR /kitty

EXPOSE 9615

ENV OPEN_TERMINAL_HOST=0.0.0.0
ENV OPEN_TERMINAL_PORT=9615

CMD open-terminal run \
    --host "$OPEN_TERMINAL_HOST" \
    --port "$OPEN_TERMINAL_PORT" \
    --api-key "$OPEN_TERMINAL_API_KEY"

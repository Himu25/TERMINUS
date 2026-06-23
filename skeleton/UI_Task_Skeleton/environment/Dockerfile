FROM node:20-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

COPY verifier-package.json /opt/ui-task-tests/package.json

RUN cd /opt/ui-task-tests \
    && npm install \
    && npx playwright install-deps chromium \
    && npx playwright install chromium

WORKDIR /app

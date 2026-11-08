FROM node:22-bookworm-slim AS node-deps
WORKDIR /build
COPY starport/package.json starport/package-lock.json ./
RUN npm ci --omit=dev

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=10000 DATA_DIR=/app/.data
WORKDIR /app
COPY --from=node-deps /usr/local/bin/node /usr/local/bin/node
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 10001 --create-home club
COPY --chown=club:club web ./web
COPY --chown=club:club server ./server
COPY --chown=club:club starport/server.mjs starport/package.json ./starport/
COPY --from=node-deps --chown=club:club /build/node_modules ./starport/node_modules
COPY --chown=club:club start.py ./
RUN mkdir .data && chown club:club .data
USER club
EXPOSE 10000
CMD ["python", "start.py"]

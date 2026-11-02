FROM node:22-bookworm-slim AS node-deps
WORKDIR /build
COPY apps/starport/package.json apps/starport/package-lock.json ./
RUN npm ci --omit=dev

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=10000
WORKDIR /app
COPY --from=node-deps /usr/local/bin/node /usr/local/bin/node
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 10001 --create-home club
COPY --chown=club:club apps ./apps
COPY --from=node-deps --chown=club:club /build/node_modules ./apps/starport/node_modules
COPY --chown=club:club start.py gateway.py ./
RUN mkdir .data && chown club:club .data
USER club
EXPOSE 10000
CMD ["python", "start.py"]

# Build context is the repository root (see docker-compose.yml).
FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ .
ARG VITE_API_BASE=/api/v1
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /app/dist /srv/www
COPY deploy/Caddyfile /etc/caddy/Caddyfile

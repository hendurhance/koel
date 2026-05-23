# syntax=docker/dockerfile:1.7

# =============================================================================
# Stage 1 — build the Nuxt app (SPA + Nitro proxy) into a standalone .output
# =============================================================================
FROM node:22-slim AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

COPY . .
RUN npm run build

# =============================================================================
# Stage 2 — runtime: node + the self-contained .output, non-root
# =============================================================================
FROM node:22-slim AS runtime

ENV NODE_ENV=production \
    NITRO_HOST=0.0.0.0 \
    NITRO_PORT=3000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --only-upgrade libgnutls30 \
    && rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx \
    && rm -rf /var/lib/apt/lists/*

# node:slim already ships a non-root `node` user (uid/gid 1000); reuse it.
COPY --from=builder --chown=node:node /app/.output ./.output

USER node

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", ".output/server/index.mjs"]

FROM node:22.22.0-alpine AS build
WORKDIR /workspace
RUN corepack enable && corepack prepare pnpm@10.28.2 --activate
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/client/package.json apps/client/package.json
COPY packages/api-client/package.json packages/api-client/package.json
COPY packages/design-tokens/package.json packages/design-tokens/package.json
COPY packages/test-utils/package.json packages/test-utils/package.json
COPY packages/translations/package.json packages/translations/package.json
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build:web

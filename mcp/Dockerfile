# Dockerfile for Glama (and anyone who wants a container): stdio MCP server.
# Read-only access to Oliver's mTOR Atlas, data from https://mtor-atlas.org/api/v1/
FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY index.js tools.js lib.js ./
ENV NODE_ENV=production
ENTRYPOINT ["node", "index.js"]

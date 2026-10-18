# ─── Build stage ──────────────────────────────
FROM node:22-alpine AS build

WORKDIR /app

# In the compose setup nginx proxies /api and /media to the backend, so the SPA
# talks to the same origin. Override at build time for split deployments.
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=$VITE_API_URL

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# ─── Serve stage ──────────────────────────────
FROM nginx:1.27-alpine AS serve

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

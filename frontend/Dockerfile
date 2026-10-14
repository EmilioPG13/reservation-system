FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Unset means "same origin, under /api", which nginx below proxies to the API. An empty value
# would not do: the client only falls back to /api when the variable is missing.
ARG VITE_API_URL
RUN [ -n "$VITE_API_URL" ] || unset VITE_API_URL; npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80

# Stage 1: build
FROM node:22-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci --silent

COPY . .
RUN npm run build

# Stage 2: serve with nginx
FROM nginx:alpine

# Vite build output → nginx html root
COPY --from=builder /app/dist /usr/share/nginx/html

# SPA routing: minden ismeretlen route → index.html
RUN echo 'server { \
    listen 80; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { try_files $uri $uri/ /index.html; } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

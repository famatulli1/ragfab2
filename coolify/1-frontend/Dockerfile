# ==========================================
# Dockerfile pour ragfab-frontend (Coolify)
# ==========================================
# Ce service expose le frontend React via Nginx
# Communication: HTTPS vers ragfab-backend

FROM node:20-alpine AS builder

WORKDIR /app

# Copier les fichiers de dépendances
COPY frontend/package*.json ./

# Installer les dépendances
RUN npm ci --production=false

# Copier le code source
COPY frontend/ ./

# Build l'application pour production
RUN npm run build

# ==========================================
# Image de production avec Nginx
# ==========================================
FROM nginx:alpine

# Installer curl pour health checks
RUN apk add --no-cache curl

# Copier la build depuis l'étape précédente
COPY --from=builder /app/dist /usr/share/nginx/html

# Copier la configuration Nginx pour Coolify
COPY coolify/1-frontend/nginx.coolify.conf /etc/nginx/conf.d/default.conf

# Créer un utilisateur non-root pour nginx
RUN addgroup -g 1000 nginx-user && \
    adduser -D -s /bin/sh -u 1000 -G nginx-user nginx-user && \
    chown -R nginx-user:nginx-user /usr/share/nginx/html /var/cache/nginx /var/log/nginx && \
    chmod -R 755 /usr/share/nginx/html

# Exposer le port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

# Démarrer Nginx (en tant que nginx-user sera fait via nginx.conf)
CMD ["nginx", "-g", "daemon off;"]

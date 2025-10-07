# Coolify utilise Caddy, pas Traefik

## 🔍 Découverte

Lors du déploiement de RAGFab sur Coolify, nous avons initialement ajouté des labels Traefik dans le `docker-compose.yml` du frontend, pensant que Coolify utilisait Traefik comme reverse proxy.

**En réalité, Coolify utilise Caddy.**

Cette découverte a été faite en inspectant le container frontend déployé:

```bash
docker inspect <frontend-container-id>
```

**Labels automatiques ajoutés par Coolify:**
```json
{
  "Labels": {
    "caddy_0": "https://www.ragbot.lab-numihfrance.fr",
    "caddy_0.encode": "zstd gzip",
    "caddy_0.handle_path": "/*",
    "caddy_0.handle_path.0_reverse_proxy": "{{upstreams}}",
    "caddy_0.header": "/*",
    "caddy_0.header.Strict-Transport-Security": "\"max-age=31536000;\"",
    "caddy_0.header.X-Content-Type-Options": "\"nosniff\"",
    "caddy_0.header.X-Frame-Options": "\"SAMEORIGIN\"",
    "caddy_0.header.X-Xss-Protection": "\"1; mode=block\"",
    "caddy_0.try_files": "{path} /index.html"
  }
}
```

## ✅ Solution

**Les labels Traefik dans docker-compose.yml ne sont pas nécessaires et ne servent à rien.**

Coolify gère automatiquement la configuration de Caddy via:
1. La configuration du domaine dans l'interface web Coolify
2. L'ajout automatique des labels Caddy aux containers
3. La génération automatique des certificats Let's Encrypt

## 🔧 Changements Appliqués

### Avant (Incorrect)
```yaml
# coolify/1-frontend/docker-compose.yml
services:
  ragfab-frontend:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.ragfab-frontend.rule=Host(`ragbot.lab-numihfrance.fr`)"
      - "traefik.http.routers.ragfab-frontend.entrypoints=websecure"
      - "traefik.http.routers.ragfab-frontend.tls=true"
      - "traefik.http.routers.ragfab-frontend.tls.certresolver=letsencrypt"
      - "traefik.http.services.ragfab-frontend.loadbalancer.server.port=80"
```

### Après (Correct)
```yaml
# coolify/1-frontend/docker-compose.yml
services:
  ragfab-frontend:
    # Note: Coolify gère automatiquement le routing HTTPS via Caddy
    # Le domaine doit être configuré dans l'interface web de Coolify
    # Pas besoin de labels ici
```

## 📋 Configuration Coolify

Pour que le routing fonctionne correctement:

1. **Interface web Coolify** → Ouvrir l'application Frontend
2. **Section "Domains"** → Ajouter le domaine `ragbot.lab-numihfrance.fr`
3. **"Enable HTTPS"** → Activé (Caddy génère automatiquement le certificat Let's Encrypt)
4. **Déployer** → Coolify ajoute automatiquement les labels Caddy

## 🔍 Comment Vérifier

### 1. Inspecter les labels d'un container
```bash
docker inspect <container-id> | grep -A 20 "Labels"
```

Vous devriez voir des labels commençant par `caddy_*`, pas `traefik.*`

### 2. Vérifier les logs du proxy Coolify
```bash
docker logs coolify-proxy
```

Recherchez des logs de Caddy concernant votre domaine.

### 3. Tester le certificat SSL
```bash
curl -v https://ragbot.lab-numihfrance.fr/health
```

Vérifiez que le certificat est émis par Let's Encrypt.

## 🎯 Architecture Finale

```
Internet (HTTPS)
    ↓
Caddy (coolify-proxy)
- Gestion des domaines
- Certificats SSL automatiques
- Reverse proxy
    ↓
Frontend Container (Nginx)
- Sert les fichiers statiques React
- Proxy /api/* → Backend
    ↓
Backend Container (FastAPI) [Privé]
- Traite les requêtes API
- Connecté à PostgreSQL et Embeddings
    ↓
PostgreSQL + Embeddings [Privés]
- Accessibles uniquement via réseau Docker
```

## 🚀 Avantages de cette Architecture

1. **Sécurité renforcée:**
   - Backend, PostgreSQL et Embeddings ne sont jamais exposés publiquement
   - Seul le frontend est accessible depuis Internet
   - Toute la logique d'authentification reste privée

2. **Simplicité:**
   - Pas besoin de gérer plusieurs domaines
   - Un seul certificat SSL (pour le frontend)
   - Configuration minimaliste

3. **Performance:**
   - Communication backend ↔ PostgreSQL ↔ Embeddings via réseau Docker (pas de HTTPS overhead)
   - Frontend ↔ Backend via proxy Nginx interne (rapide)

4. **Maintenance:**
   - Coolify gère automatiquement le renouvellement SSL
   - Pas de configuration Traefik/Caddy manuelle
   - Déploiements reproductibles

## 📚 Documentation Officielle

- [Coolify Docs - Domains](https://coolify.io/docs/knowledge-base/domains)
- [Coolify Docs - SSL](https://coolify.io/docs/knowledge-base/ssl)
- [Caddy Docs - Reverse Proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)

## 🆘 Troubleshooting

### Problème: 404 même après déploiement

**Vérifiez:**
1. Le domaine est bien configuré dans Coolify UI (section "Domains")
2. Le DNS pointe vers l'IP du serveur: `dig ragbot.lab-numihfrance.fr`
3. Les ports 80 et 443 sont ouverts: `sudo ufw status`
4. Caddy a généré le certificat: `docker logs coolify-proxy | grep ragbot`

### Problème: Certificat SSL invalide

**Solution:**
1. Vérifiez que "Enable HTTPS" est activé dans Coolify
2. Attendez quelques minutes (génération du certificat)
3. Vérifiez les logs Caddy: `docker logs coolify-proxy`
4. Assurez-vous que Let's Encrypt peut accéder au serveur (pas de firewall bloquant)

### Problème: 502 Bad Gateway

**Cause probable:** Le backend n'est pas accessible depuis le frontend

**Solution:**
1. Vérifiez que les deux services sont sur le réseau `coolify`:
   ```bash
   docker network inspect coolify
   ```
2. Vérifiez que le backend est nommé `ragfab-backend` (configuration dans docker-compose.yml)
3. Testez la connectivité:
   ```bash
   docker exec <frontend-container-id> wget -qO- http://ragfab-backend:8000/health
   ```

## ✅ Checklist de Déploiement

Avant de considérer le déploiement comme réussi:

- [ ] Frontend accessible via `https://ragbot.lab-numihfrance.fr`
- [ ] Certificat SSL valide (Let's Encrypt)
- [ ] Health check frontend: `curl https://ragbot.lab-numihfrance.fr/health` → "healthy"
- [ ] Health check backend: `curl https://ragbot.lab-numihfrance.fr/api/health` → {"status":"healthy"}
- [ ] Backend NOT accessible publiquement (erreur de connexion sur port 8000 depuis Internet)
- [ ] PostgreSQL NOT accessible publiquement (erreur de connexion sur port 5432 depuis Internet)
- [ ] Embeddings NOT accessible publiquement (erreur de connexion sur port 8001 depuis Internet)

Si tous les points sont validés, le déploiement est correct et sécurisé ! 🎉

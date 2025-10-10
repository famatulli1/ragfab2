# Guide Migration Reranker CPU → GPU

## 🎯 Objectif

Migrer le service `reranker` d'un serveur CPU vers un serveur GPU pour améliorer drastiquement les performances.

---

## 📊 Gains Attendus

### Performance Reranking

| Métrique | CPU (Actuel) | GPU (Hetzner T4) | Gain |
|----------|--------------|------------------|------|
| **Latence par requête** | 200-500ms | **50-150ms** | **-60-70%** ⚡ |
| **Throughput** | 5-10 req/s | **50-100 req/s** | **+900%** |
| **Batch 20 candidats** | 200-500ms | **50-150ms** | **3-4x plus rapide** |
| **Batch 50 candidats** | 800ms-1.5s | **100-200ms** | **5-7x plus rapide** |

### Impact Utilisateur Final

| Mode | CPU | GPU | Amélioration |
|------|-----|-----|--------------|
| **Mode rapide (OFF)** | 1-2s | 1-2s | Identique |
| **Mode précis (ON)** | 2-4s | **1.5-2.5s** | **-25-40%** |
| **Activation par défaut viable** | ❌ Non | ✅ **OUI** | Qualité +20-30% sans pénalité |

---

## 💰 Coût Infrastructure

### Options Serveur GPU

| Provider | GPU | Prix/mois | RAM | vCPU | Recommandation |
|----------|-----|-----------|-----|------|----------------|
| **Hetzner Cloud** | Tesla T4 | **~40€** | 32GB | 8 vCPU | ⭐ **MEILLEUR RAPPORT QUALITÉ/PRIX** |
| **OVHcloud** | V100 | ~100€ | 32GB | 8 vCPU | Performant mais cher |
| **Scaleway** | V100 | ~80€ | 64GB | 16 vCPU | Bon compromis |
| **AWS g4dn.xlarge** | T4 | ~120€ | 16GB | 4 vCPU | Cher, mais fiable |
| **Azure NC4as T4** | T4 | ~150€ | 28GB | 4 vCPU | Très cher |

**Recommandation** : **Hetzner Cloud avec Tesla T4** - Largement suffisant pour BGE-reranker-v2-m3, excellent rapport qualité/prix.

---

## 🏗️ Architecture Recommandée

### Option 1 : Serveur GPU Dédié (RECOMMANDÉ)

```
┌─────────────────────────────────────────────┐
│ Serveur Principal (CPU) - Coolify          │
│                                             │
│  ├─ postgres                                │
│  ├─ embeddings (CPU)                        │
│  ├─ ragfab-api                              │
│  ├─ frontend                                │
│  └─ ingestion-worker                        │
│                                             │
│  RERANKER_API_URL=http://<GPU_IP>:8002     │
└─────────────────────────────────────────────┘
                    ↓
                    │ HTTP
                    ↓
┌─────────────────────────────────────────────┐
│ Serveur GPU (Hetzner T4)                    │
│                                             │
│  └─ reranker-gpu (CUDA-accelerated)        │
│     - Port 8002 exposé                      │
│     - DEVICE=cuda                           │
│     - ~2-3GB VRAM utilisés                  │
└─────────────────────────────────────────────┘
```

**Avantages** :
- ✅ Pas de migration du serveur principal
- ✅ Coût optimisé : GPU uniquement pour reranker
- ✅ Scaling indépendant (peut ajouter plusieurs GPUs)
- ✅ Rollback facile si problème
- ✅ Pas d'impact sur les autres services

---

## 📝 Étape 1 : Préparer Serveur GPU

### 1.1 Provisionner Serveur Hetzner

**Specs recommandées** :
```
Type: CCX33
GPU: 1x Tesla T4 (16GB VRAM)
CPU: 8 vCPU
RAM: 32GB
Storage: 240GB SSD
OS: Ubuntu 22.04 LTS
Prix: ~40€/mois
```

**Configuration initiale** :
```bash
# SSH sur serveur GPU
ssh root@<GPU_SERVER_IP>

# Mettre à jour système
apt update && apt upgrade -y

# Installer NVIDIA drivers
apt install -y nvidia-driver-535 nvidia-utils-535

# Vérifier GPU détecté
nvidia-smi

# Attendu : Tesla T4, CUDA Version: 12.2+
```

---

### 1.2 Installer Docker avec Support GPU

```bash
# Installer Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Installer NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
    gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

apt update
apt install -y nvidia-container-toolkit

# Configurer Docker pour GPU
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker

# Tester Docker GPU
docker run --rm --gpus all nvidia/cuda:12.1.0-runtime-ubuntu22.04 nvidia-smi

# Attendu : Affichage info GPU
```

---

## 📝 Étape 2 : Déployer Reranker GPU

### 2.1 Transférer Code Reranker

```bash
# Depuis serveur principal ou machine locale
scp -r ./reranker-server root@<GPU_SERVER_IP>:/root/

# SSH sur serveur GPU
ssh root@<GPU_SERVER_IP>
cd /root/reranker-server
```

---

### 2.2 Créer docker-compose.gpu.yml

```yaml
# /root/reranker-server/docker-compose.gpu.yml
version: '3.8'

services:
  reranker-gpu:
    build:
      context: .
      dockerfile: Dockerfile.gpu
    container_name: reranker-gpu
    environment:
      RERANKER_MODEL: BAAI/bge-reranker-v2-m3
      DEVICE: cuda  # Force GPU usage
    ports:
      - "8002:8002"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 120s
```

---

### 2.3 Modifier app.py pour Forcer GPU

```bash
# Vérifier que app.py utilise bien le device
nano /root/reranker-server/app.py
```

**Ajouter détection GPU explicite** :
```python
import torch
import logging

logger = logging.getLogger(__name__)

# Forcer GPU si disponible
if torch.cuda.is_available():
    device = "cuda"
    logger.info(f"🚀 GPU détecté: {torch.cuda.get_device_name(0)}")
    logger.info(f"💾 VRAM disponible: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
else:
    device = "cpu"
    logger.warning("⚠️ GPU non détecté, utilisation CPU")

# Charger modèle sur GPU
model = CrossEncoder(MODEL_NAME, max_length=512, device=device)
```

---

### 2.4 Build et Démarrage

```bash
# Build image GPU
docker compose -f docker-compose.gpu.yml build

# Démarrer service
docker compose -f docker-compose.gpu.yml up -d

# Vérifier logs
docker compose -f docker-compose.gpu.yml logs -f

# Attendu :
# 🚀 GPU détecté: Tesla T4
# 💾 VRAM disponible: 15.00 GB
# ✅ Reranker service started on port 8002
```

---

### 2.5 Tester Service GPU

```bash
# Test healthcheck
curl http://localhost:8002/health

# Attendu : {"status": "healthy", "device": "cuda", "model": "BAAI/bge-reranker-v2-m3"}

# Test reranking (depuis serveur GPU)
curl -X POST http://localhost:8002/rerank \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Comment résoudre erreur fusappel 6102?",
    "documents": [
      {"content": "Erreur fusappel 6102: vérifier configuration", "metadata": {}},
      {"content": "Documentation fusappel", "metadata": {}}
    ]
  }'

# Attendu : Réponse en 50-150ms avec scores
```

---

## 📝 Étape 3 : Configurer Serveur Principal

### 3.1 Modifier Variables Coolify

**Service : `ragfab-api`**

Coolify → Service `ragfab-api` → Environment Variables :

```bash
# Avant (CPU local)
RERANKER_API_URL=http://reranker:8002  # Service local

# Après (GPU distant)
RERANKER_API_URL=http://<GPU_SERVER_IP>:8002  # Serveur GPU externe

# Paramètres optimisés pour GPU
RERANKER_ENABLED=true   # Redevient viable !
RERANKER_TOP_K=30       # Peut augmenter sans pénalité
RERANKER_RETURN_K=10    # Plus de contexte LLM
```

**Remplacer `<GPU_SERVER_IP>` par l'IP publique du serveur Hetzner.**

---

### 3.2 Firewall Serveur GPU

```bash
# SSH sur serveur GPU
ssh root@<GPU_SERVER_IP>

# Autoriser port 8002 depuis serveur principal uniquement (sécurité)
ufw allow from <SERVEUR_PRINCIPAL_IP> to any port 8002

# OU ouvrir à tous (moins sécurisé mais plus simple)
ufw allow 8002/tcp

# Activer firewall
ufw enable
```

---

### 3.3 Redémarrer ragfab-api

```bash
# Via Coolify UI
Service ragfab-api → Restart

# Vérifier logs
docker logs -f ragfab-api | grep -i rerank

# Attendu :
# ✅ Reranker service accessible at http://<GPU_IP>:8002
# 🔄 Reranking activé par défaut
```

---

## 🧪 Tests Validation

### Test 1 : Vérifier Connexion GPU

```bash
# Depuis serveur principal
curl http://<GPU_SERVER_IP>:8002/health

# Attendu : {"status": "healthy", "device": "cuda"}
```

---

### Test 2 : Mesurer Latence Reranking

**Avant (CPU)** :
```bash
time curl -X POST http://localhost:8002/rerank \
  -H "Content-Type: application/json" \
  -d @test_rerank.json

# Attendu : 200-500ms
```

**Après (GPU)** :
```bash
time curl -X POST http://<GPU_SERVER_IP>:8002/rerank \
  -H "Content-Type: application/json" \
  -d @test_rerank.json

# Attendu : 50-150ms ⚡ (3-4x plus rapide)
```

---

### Test 3 : Test Utilisateur Final

**Avec reranking activé par défaut** :
```
1. Ouvrir nouvelle conversation (toggle "Recherche approfondie" absent ou toujours ON)
2. Poser question : "Comment résoudre l'erreur fusappel 6102 ?"
3. Mesurer temps réponse
```

**Résultat attendu** :
- ✅ Temps réponse : **1.5-2.5s** (au lieu de 2-4s avec CPU)
- ✅ Qualité : +20-30% précision (reranking systématique)
- ✅ Logs : `"🔄 Reranking GPU: 20 candidats → 10 résultats en 80ms"`

---

### Test 4 : Monitoring GPU

```bash
# SSH sur serveur GPU
watch -n 1 nvidia-smi

# Observer pendant requêtes :
# - GPU Utilization: ~30-50% par requête
# - Memory Used: ~2-3GB VRAM
# - Temperature: ~50-60°C (normal)
```

---

## 📊 Résultats Attendus

### Performance

| Métrique | CPU | GPU | Gain |
|----------|-----|-----|------|
| **Latence mode précis** | 2-4s | **1.5-2.5s** | **-25-40%** |
| **Latence reranking seul** | 200-500ms | **50-150ms** | **-60-70%** |
| **Throughput multi-users** | 5-10 req/s | **50-100 req/s** | **+900%** |
| **Batch 50 candidats** | 800ms-1.5s | **100-200ms** | **5-7x** |

### Coût

| Élément | Coût Mensuel |
|---------|--------------|
| **Serveur GPU Hetzner T4** | ~40€ |
| **Trafic réseau** | ~2-5€ (négligeable) |
| **Total** | **~45€/mois** |

**ROI** : Si >10 utilisateurs actifs ou si qualité +20-30% justifie 45€/mois.

---

## 🎯 Recommandation Finale

### ✅ OUI, migrer sur GPU si :

1. **Budget disponible** : 40-50€/mois acceptable
2. **Multi-utilisateurs** : >5 utilisateurs simultanés prévus
3. **Qualité prioritaire** : Reranking systématique souhaité sans pénalité latence
4. **Scaling futur** : Prévision charge importante

### ❌ Non, rester sur CPU si :

1. **Budget serré** : 40€/mois non justifiable
2. **Usage limité** : <5 utilisateurs, quelques requêtes/jour
3. **Mode manuel acceptable** : Toggle "Recherche approfondie" suffit
4. **Prototype/MVP** : Pas encore en production

---

## 🚀 Alternative : Optimisations CPU Sans GPU

Si budget limité, optimisations CPU possibles :

### 1. Quantization INT8

```python
# Dans app.py
from optimum.onnxruntime import ORTModelForSequenceClassification

# Charger modèle quantizé (2x plus rapide sur CPU)
model = ORTModelForSequenceClassification.from_pretrained(
    "BAAI/bge-reranker-v2-m3",
    export=True,
    provider="CPUExecutionProvider"
)
```

**Gain attendu** : -30-40% latence (300-350ms → 180-210ms)

---

### 2. Batch Processing Optimisé

```python
# Traiter candidats par batch de 10 au lieu de 20
# Compromis latence/qualité
RERANKER_TOP_K=10  # Au lieu de 20
RERANKER_RETURN_K=5
```

**Gain attendu** : -40-50% latence (400ms → 200-240ms)

---

### 3. Caching Résultats

```python
# Cache Redis pour queries fréquentes
# Évite reranking pour questions identiques
from redis import Redis

cache = Redis(host='localhost', port=6379, db=0)

def rerank_with_cache(query, docs):
    cache_key = f"rerank:{hash(query)}"
    cached = cache.get(cache_key)
    if cached:
        return json.loads(cached)

    results = rerank(query, docs)
    cache.setex(cache_key, 3600, json.dumps(results))  # TTL 1h
    return results
```

**Gain** : 0ms pour queries en cache (hit rate ~20-30% en production)

---

## 📚 Fichiers Créés

1. [reranker-server/Dockerfile.gpu](reranker-server/Dockerfile.gpu) - Dockerfile CUDA
2. [GPU_MIGRATION_GUIDE.md](GPU_MIGRATION_GUIDE.md) - Ce guide (nouveau)

---

## ✅ Checklist Migration GPU

### Préparation
- [ ] Provisionner serveur GPU Hetzner (Tesla T4, ~40€/mois)
- [ ] Installer NVIDIA drivers + Docker GPU support
- [ ] Tester `nvidia-smi` et `docker run --gpus all`

### Déploiement Reranker GPU
- [ ] Transférer code reranker sur serveur GPU
- [ ] Build image avec `Dockerfile.gpu`
- [ ] Démarrer service avec `docker-compose.gpu.yml`
- [ ] Vérifier logs : "GPU détecté: Tesla T4"
- [ ] Test healthcheck : `curl http://localhost:8002/health`

### Configuration Serveur Principal
- [ ] Modifier `RERANKER_API_URL` vers IP serveur GPU
- [ ] Ajuster `RERANKER_ENABLED=true` (activation par défaut)
- [ ] Augmenter `RERANKER_TOP_K=30`, `RERANKER_RETURN_K=10`
- [ ] Configurer firewall serveur GPU (port 8002)
- [ ] Redémarrer `ragfab-api`

### Tests Validation
- [ ] Connexion réseau : `curl http://<GPU_IP>:8002/health`
- [ ] Latence reranking : 50-150ms confirmé
- [ ] Test utilisateur : Temps réponse 1.5-2.5s
- [ ] Monitoring GPU : VRAM ~2-3GB, utilisation 30-50%

### Production
- [ ] Monitoring latence : Dashboard Grafana/Prometheus
- [ ] Alertes : Service reranker down, latence >500ms
- [ ] Backup config : `docker-compose.gpu.yml` versionné
- [ ] Documentation équipe : URL reranker, procédure rollback

---

**Date création** : 2025-01-10
**Auteur** : Claude Code
**Version** : 1.0 - Guide Migration Reranker GPU

# Guide d'Activation du Reranking RAGFab

Guide rapide pour activer et utiliser le système de reranking dans RAGFab.

## 🚀 Démarrage Rapide

### 1. Configurer les Variables d'Environnement

Copier `.env.example` vers `.env` (si pas déjà fait) et configurer le reranking :

```bash
# Dans votre fichier .env

# Configuration globale (optionnelle)
RERANKER_ENABLED=false  # Par défaut, désactivé globalement
RERANKER_API_URL=http://reranker:8002
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_TOP_K=20
RERANKER_RETURN_K=5
```

**Note** : Avec le nouveau système de toggle par conversation, vous pouvez laisser `RERANKER_ENABLED=false` globalement et activer le reranking uniquement pour les conversations qui en ont besoin via l'interface web.

### 2. Démarrer les Services

```bash
# Démarrer tous les services incluant le reranker
docker-compose up -d postgres embeddings reranker

# Puis démarrer l'API web
docker-compose up -d ragfab-api

# Optionnel : démarrer le frontend
docker-compose up -d ragfab-frontend
```

### 3. Vérifier que le Reranker Fonctionne

```bash
# Healthcheck
curl http://localhost:8002/health

# Devrait retourner:
# {"status": "healthy", "model": "BAAI/bge-reranker-v2-m3"}
```

### 4. Vérifier les Logs

```bash
# Observer le démarrage du reranker
docker-compose logs -f reranker

# Vous devriez voir:
# INFO: Chargement du modèle BAAI/bge-reranker-v2-m3...
# INFO: Modèle de reranking chargé en XX.XXs

# Observer l'utilisation en temps réel
docker-compose logs -f ragfab-api

# Cherchez les logs:
# 🔄 Reranking activé: recherche de 20 candidats
# 🎯 Application du reranking sur 20 candidats
# ✅ Reranking effectué en 0.XXXs, 5 documents retournés
```

## 🎚️ Toggle Reranking Par Conversation (NOUVEAU)

### Utilisation du Toggle dans l'Interface Web

Le système de reranking peut désormais être contrôlé **par conversation** directement depuis le frontend, sans redémarrage de l'API !

#### Interface

Dans l'en-tête de chaque conversation, vous trouverez un bouton **"Reranking"** avec trois états possibles :

**État 1 : 🌐 Gris - "Reranking: Global"**
- Utilise la valeur de la variable d'environnement `RERANKER_ENABLED`
- Comportement par défaut pour les nouvelles conversations
- Cliquez pour passer à l'état "ON"

**État 2 : 🟢 Vert - "Reranking: ON"**
- Force l'activation du reranking pour cette conversation
- Ignore la variable d'environnement globale
- Cliquez pour passer à l'état "OFF"

**État 3 : 🔴 Rouge - "Reranking: OFF"**
- Force la désactivation du reranking pour cette conversation
- Ignore la variable d'environnement globale
- Cliquez pour revenir à l'état "Global"

#### Cycle de Changement d'État

```
NULL (🌐 Gris) → TRUE (🟢 Vert) → FALSE (🔴 Rouge) → NULL (🌐 Gris) ...
```

#### Cas d'Usage

**Scénario 1 : Tests A/B**
```
1. Laisser RERANKER_ENABLED=false globalement
2. Créer deux conversations
3. Activer le reranking (🟢 vert) sur la première
4. Laisser en mode global (🌐 gris) sur la deuxième
5. Comparer les résultats pour la même question
```

**Scénario 2 : Documentation Mixte**
```
1. RERANKER_ENABLED=false globalement
2. Conversation A (FAQ simple) : Laisser en gris (désactivé globalement)
3. Conversation B (doc technique complexe) : Passer en vert (activé)
4. Chaque conversation a le comportement optimal
```

**Scénario 3 : Économie de Ressources**
```
1. RERANKER_ENABLED=true globalement (pour les conversations importantes)
2. Conversation rapide : Passer en rouge pour forcer la désactivation
3. Gain de ~200ms par requête sur cette conversation
```

#### Persistance

La préférence de reranking est **sauvegardée dans la base de données** :
- Survit aux redémarrages de l'API
- Indépendante des variables d'environnement
- Visible dans toutes les instances de l'API

#### Logs de Débogage

Lorsque vous utilisez le toggle, observez les logs pour confirmer :

```bash
docker-compose logs -f ragfab-api | grep reranking

# Avec toggle VERT (activé) :
# 🎚️ Préférence conversation <UUID>: reranking=True
# 🔄 Reranking activé: recherche de 20 candidats

# Avec toggle ROUGE (désactivé) :
# 🎚️ Préférence conversation <UUID>: reranking=False
# 📊 Reranking désactivé: recherche vectorielle directe (top-5)

# Avec toggle GRIS (global) :
# 🌐 Préférence globale (env): reranking=<valeur de RERANKER_ENABLED>
```

### Migration de la Base de Données

Si vous mettez à jour depuis une version précédente, appliquez la migration :

```bash
docker exec -i ragfab-postgres psql -U raguser -d ragdb < database/03_reranking_migration.sql
```

Vérification :

```bash
docker exec ragfab-postgres psql -U raguser -d ragdb -c "\d conversations"

# Vous devriez voir la colonne:
# reranking_enabled | boolean | | |
```

## 🔧 Configuration Avancée

### Ajuster le Nombre de Candidats

Pour documentation très technique avec beaucoup de terminologie similaire :

```bash
RERANKER_TOP_K=30      # Récupérer plus de candidats
RERANKER_RETURN_K=3    # Mais retourner seulement les 3 meilleurs
```

Pour documentation plus simple :

```bash
RERANKER_TOP_K=15      # Moins de candidats = plus rapide
RERANKER_RETURN_K=5    # 5 résultats finaux
```

### Performance vs Précision

| Configuration | Latence | Précision | Use Case |
|---------------|---------|-----------|----------|
| TOP_K=10, RETURN_K=3 | ~100ms | Bonne | Documentation simple |
| TOP_K=20, RETURN_K=5 | ~200ms | Excellente | **Recommandé** |
| TOP_K=30, RETURN_K=3 | ~300ms | Maximale | Documentation médicale complexe |

### Ajuster les Ressources Docker

Si vous avez des contraintes de mémoire :

```yaml
# Dans docker-compose.yml, section reranker
deploy:
  resources:
    limits:
      cpus: '1'      # Réduire de 2 à 1 CPU
      memory: 3G     # Réduire de 4G à 3G
```

**Note**: Le modèle nécessite minimum 2GB RAM. Ne pas descendre en dessous.

## 🧪 Tester le Reranking

### Test avec Documentation Médicale

1. **Ingérer des documents médicaux** :
```bash
# Placer vos PDFs médicaux dans rag-app/documents/
docker-compose --profile app run --rm rag-app python -m ingestion.ingest
```

2. **Poser une question technique** :
```
"Quel est le protocole de traitement pour l'hypertension artérielle ?"
```

3. **Observer les logs** :
```bash
docker-compose logs ragfab-api | grep -A 5 "Reranking"

# Vous verrez:
# 🔄 Reranking activé: recherche de 20 candidats
# 🎯 Application du reranking sur 20 candidats
# ✅ Reranking effectué en 0.234s, 5 documents retournés
```

### Comparer Avec/Sans Reranking

**Test A : Sans reranking**
```bash
# Dans .env
RERANKER_ENABLED=false

# Poser la question
# Noter les sources retournées
```

**Test B : Avec reranking**
```bash
# Dans .env
RERANKER_ENABLED=true

# Relancer ragfab-api
docker-compose restart ragfab-api

# Poser la MÊME question
# Comparer les sources retournées
```

Vous devriez observer :
- Sources plus pertinentes avec reranking
- Moins de "faux positifs" (documents similaires mais hors sujet)
- Latence légèrement supérieure (+100-200ms)

## 🔴 Désactiver le Reranking

Pour revenir au mode vector search simple :

```bash
# Dans .env
RERANKER_ENABLED=false

# Redémarrer l'API
docker-compose restart ragfab-api

# Le service reranker peut rester actif (pas utilisé) ou être arrêté:
docker-compose stop reranker
```

## 📊 Monitoring

### Métriques à Observer

**Latence** :
```bash
# Logs ragfab-api
docker-compose logs ragfab-api | grep "Reranking effectué"

# Temps typiques:
# 10 docs: ~100ms
# 20 docs: ~200ms
# 30 docs: ~300ms
```

**Ressources** :
```bash
# CPU et RAM du service reranker
docker stats ragfab-reranker

# Valeurs typiques au repos:
# CPU: 0.5-1%
# RAM: ~2-3GB (modèle chargé)

# Valeurs pendant reranking:
# CPU: 50-100% (burst)
# RAM: ~3-4GB
```

**Erreurs** :
```bash
# Chercher les fallbacks (erreurs gracieuses)
docker-compose logs ragfab-api | grep "fallback"

# Si vous voyez des fallbacks fréquents:
# - Vérifier que le service reranker est up
# - Augmenter le timeout (actuellement 60s)
# - Vérifier les ressources disponibles
```

## 🐛 Troubleshooting

### Le service reranker ne démarre pas

**Symptôme** : `docker-compose logs reranker` montre des erreurs

**Solutions** :
```bash
# 1. Vérifier la mémoire disponible
docker stats

# 2. Le modèle nécessite au moins 2GB RAM libre
# Libérer de la mémoire ou augmenter les limites Docker

# 3. Rebuild l'image
docker-compose build reranker
docker-compose up -d reranker
```

### Timeout lors du reranking

**Symptôme** : Logs montrent "⚠️ Erreur lors du reranking (fallback vers vector search)"

**Solutions** :
```bash
# 1. Réduire RERANKER_TOP_K
RERANKER_TOP_K=15  # Au lieu de 20

# 2. Augmenter le timeout dans web-api/app/main.py
# Ligne ~814: timeout=90.0 (au lieu de 60.0)

# 3. Vérifier les ressources CPU
docker stats ragfab-reranker
```

### Résultats identiques avec/sans reranking

**Symptôme** : Pas de différence notable dans les sources

**Causes possibles** :
1. **Documents trop similaires** : Le vector search était déjà excellent
2. **Base documentaire petite** : <50 documents, le reranking n'apporte pas beaucoup
3. **Questions simples** : Questions avec mots-clés clairs

**Solution** : Le reranking est surtout utile pour :
- Documentation technique dense
- Terminologie similaire (médical, juridique)
- Grandes bases (>500 documents)
- Questions complexes ou ambiguës

### Fallback systématique vers vector search

**Symptôme** : Tous les logs montrent "fallback vers vector search"

**Diagnostic** :
```bash
# Vérifier que le service est accessible
curl http://localhost:8002/health

# Si erreur de connexion:
docker-compose ps | grep reranker

# Le conteneur doit être "Up"
# Sinon:
docker-compose up -d reranker
```

## 💡 Cas d'Usage Recommandés

### ✅ Activer le Reranking Pour

1. **Documentation médicale** :
   - Pathologies, traitements, protocoles
   - Terminologie technique dense
   - Beaucoup de concepts liés

2. **Documentation juridique** :
   - Codes, lois, jurisprudence
   - Références croisées nombreuses
   - Nuances critiques

3. **Documentation scientifique** :
   - Articles de recherche
   - Terminologie spécialisée
   - Concepts abstraits similaires

4. **Bases documentaires larges** :
   - >1000 documents
   - Domaines multiples
   - Risque de confusion élevé

### ❌ Pas Besoin du Reranking Pour

1. **Documentation simple** :
   - Guides utilisateur basiques
   - FAQ simples
   - Contenus distincts

2. **Petites bases** :
   - <100 documents
   - Domaine unique bien défini
   - Questions simples

3. **Contraintes de latence strictes** :
   - Besoin de <100ms de réponse
   - Chatbots temps réel
   - Applications interactives rapides

## 🔄 Workflow de Développement

### Cycle de développement typique

1. **Développement initial** : RERANKER_ENABLED=false
   - Tests rapides
   - Itérations fréquentes
   - Pas besoin de précision maximale

2. **Tests fonctionnels** : RERANKER_ENABLED=true
   - Valider la pertinence
   - Ajuster TOP_K et RETURN_K
   - Mesurer la latence

3. **Production** : RERANKER_ENABLED=true (si pertinent)
   - Activer pour documentation technique
   - Monitoring actif
   - Fallback gracieux en place

## 📈 Amélioration Continue

### Métriques à Tracker

1. **Satisfaction utilisateur** :
   - Thumbs up/down sur les réponses
   - Feedback qualitatif
   - Taux de reformulation de questions

2. **Pertinence des sources** :
   - Sources cliquées vs affichées
   - Temps passé sur les sources
   - Relevance ratings

3. **Performance** :
   - Latence p50, p95, p99
   - Taux de fallback
   - Utilisation ressources

### Optimisation

Si le reranking ne semble pas améliorer les résultats :

1. **Augmenter TOP_K** : Donner plus de candidats au reranker
2. **Ajuster RETURN_K** : Retourner moins de résultats mais plus sûrs
3. **Vérifier les embeddings** : Le vector search initial est-il bon ?
4. **Analyser les questions** : Sont-elles techniques ou simples ?

## 🎓 Ressources

- [Documentation BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3)
- [Service Reranker README](reranker-server/README.md)
- [CLAUDE.md - Section Reranking](CLAUDE.md#reranking-system-new)
- [Documentation RAGFab complète](README.md)

## ✉️ Support

En cas de problème :
1. Vérifier les logs : `docker-compose logs -f reranker ragfab-api`
2. Vérifier les healthchecks : `curl http://localhost:8002/health`
3. Consulter le troubleshooting ci-dessus
4. Ouvrir une issue GitHub avec les logs pertinents

# 🚀 QuickStart - RAGFab

Guide de démarrage rapide pour RAGFab.

---

## ✅ Étapes rapides (5 minutes)

### 1. Cloner le projet

```bash
git clone https://github.com/famatulli1/ragfab.git
cd ragfab
```

### 2. Configurer l'environnement

```bash
cp .env.example .env
```

Éditez `.env` et mettez à jour :
- `CHOCOLATINE_API_URL` : URL de votre API Chocolatine (par défaut : `https://apigpt.mynumih.fr`)
- `CHOCOLATINE_API_KEY` : Votre clé API si nécessaire

**Les autres variables peuvent rester par défaut pour un test local.**

### 3. Démarrer les services

```bash
docker-compose up -d
```

⏱️ **Attention** : Le premier démarrage prend 5-10 minutes (téléchargement du modèle d'embeddings ~2.2GB)

### 4. Vérifier que tout fonctionne

```bash
# Vérifier les services
docker-compose ps

# Tester le serveur d'embeddings
curl http://localhost:8001/health

# Vérifier PostgreSQL
docker exec -it ragfab-postgres psql -U raguser -d ragdb -c "\dt"
```

### 5. Ingérer des documents

Ajoutez vos documents dans `rag-app/documents/` puis :

```bash
docker-compose run --rm rag-app python -m ingestion.ingest --documents /app/documents
```

### 6. Lancer l'agent RAG

```bash
docker-compose --profile app up rag-app
```

Interagissez avec l'agent :

```
Vous: Quels sont les sujets abordés dans la documentation ?
Assistant: [Réponse basée sur vos documents]

Vous: quit
```

---

## 🎯 Architecture simplifiée

```
Votre machine
├── PostgreSQL + PGVector (port 5432)
├── Serveur Embeddings (port 8001)
│   └── multilingual-e5-large (1024 dim)
└── Application RAG
    ├── Ingestion de documents
    └── Agent conversationnel
        └── Utilise Chocolatine-2-14B (via votre API)
```

---

## 🛠️ Commandes utiles

### Gérer les services

```bash
# Démarrer
docker-compose up -d

# Arrêter
docker-compose down

# Voir les logs
docker-compose logs -f embeddings
docker-compose logs -f postgres

# Redémarrer un service
docker-compose restart embeddings
```

### Ingestion

```bash
# Ingérer tous les documents
docker-compose run --rm rag-app python -m ingestion.ingest --documents /app/documents

# Avec chunk size personnalisé
docker-compose run --rm rag-app python -m ingestion.ingest --documents /app/documents --chunk-size 1500

# Vérifier les documents ingérés
docker exec -it ragfab-postgres psql -U raguser -d ragdb -c "SELECT title, COUNT(*) as chunks FROM documents d JOIN chunks c ON d.id = c.document_id GROUP BY d.id, d.title;"
```

### Base de données

```bash
# Se connecter à PostgreSQL
docker exec -it ragfab-postgres psql -U raguser -d ragdb

# Compter les documents
docker exec -it ragfab-postgres psql -U raguser -d ragdb -c "SELECT COUNT(*) FROM documents;"

# Compter les chunks
docker exec -it ragfab-postgres psql -U raguser -d ragdb -c "SELECT COUNT(*) FROM chunks;"

# Vider la base (⚠️ supprime tout)
docker exec -it ragfab-postgres psql -U raguser -d ragdb -c "TRUNCATE chunks, documents CASCADE;"
```

---

## 📊 Performance attendue

### Serveur d'embeddings (CPU)
- **Latence** : 50-200ms par embedding
- **Batch de 100** : ~2-5 secondes
- **RAM** : 4-6 GB

### Ingestion
- **~10 documents** : 1-2 minutes
- **~100 documents** : 10-15 minutes
- Dépend de la taille des documents

### Requêtes RAG
- **Recherche vectorielle** : 10-50ms
- **Génération de réponse** : Dépend de votre API Chocolatine

---

## 🚨 Dépannage rapide

### Le serveur d'embeddings ne démarre pas

```bash
# Voir les logs
docker-compose logs embeddings

# Vérifier l'espace disque (modèle = 2.2GB)
df -h

# Redémarrer
docker-compose restart embeddings
```

### Erreur "Module not found"

```bash
# Reconstruire l'image rag-app
docker-compose build rag-app

# Relancer l'ingestion
docker-compose run --rm rag-app python -m ingestion.ingest --documents /app/documents
```

### PostgreSQL ne répond pas

```bash
# Vérifier les logs
docker-compose logs postgres

# Redémarrer
docker-compose restart postgres

# Vérifier la connexion
docker exec -it ragfab-postgres psql -U raguser -d ragdb -c "SELECT 1;"
```

### L'agent ne trouve rien

```bash
# Vérifier que des documents sont ingérés
docker exec -it ragfab-postgres psql -U raguser -d ragdb -c "SELECT COUNT(*) FROM chunks;"

# Vérifier que les embeddings sont présents
docker exec -it ragfab-postgres psql -U raguser -d ragdb -c "SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL;"

# Ré-ingérer si nécessaire
docker-compose run --rm rag-app python -m ingestion.ingest --documents /app/documents
```

---

## 🚀 Déploiement sur Coolify

1. Pushez votre code sur GitHub (déjà fait : `github.com/famatulli1/ragfab`)

2. Dans Coolify :
   - Nouveau projet → Connecter le repo
   - Sélectionner `docker-compose.coolify.yml`
   - Configurer les variables d'environnement (voir `.env.example`)
   - Déployer

3. Notez les URLs internes générées par Coolify

4. Pour l'ingestion (depuis votre machine locale) :
   ```bash
   # Mettre à jour .env avec les URLs Coolify
   DATABASE_URL=postgresql://user:pass@db.coolify.internal:5432/ragdb
   EMBEDDINGS_API_URL=http://embeddings.coolify.internal:8001

   # Ingérer
   docker-compose run --rm rag-app python -m ingestion.ingest --documents /app/documents
   ```

---

## 📚 Documentation complète

- [README.md](README.md) - Documentation détaillée
- [GUIDE_TEST.md](GUIDE_TEST.md) - Tests complets
- `.env.example` - Toutes les variables de configuration

---

## 💡 Bonnes pratiques

### Formats de documents supportés

✅ **Bien supportés** :
- PDF, Word, PowerPoint
- Markdown, Texte brut
- HTML

⚠️ **À préparer** :
- Images scannées → OCR avant ingestion
- Tableaux complexes → Peuvent nécessiter un chunking personnalisé

### Taille des chunks

- **Petits (500-800)** : Précision élevée, mais contexte limité
- **Moyens (1000-1500)** : ✅ **Recommandé** - Bon équilibre
- **Grands (2000-3000)** : Plus de contexte, mais moins précis

### Nombre de résultats (limit)

- **3-5 résultats** : ✅ **Recommandé** - Rapide et pertinent
- **10+ résultats** : Plus de contexte, mais plus lent et parfois bruyant

---

**Besoin d'aide ?** Consultez le [README.md](README.md) ou ouvrez une issue sur GitHub.

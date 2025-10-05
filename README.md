# 🇫🇷 RAGFab - Système RAG Français avec Chocolatine-2-14B

Système RAG (Retrieval Augmented Generation) **100% autonome** et **optimisé pour le français**, utilisant :
- **Chocolatine-2-14B** (Top 3 French LLM) comme modèle de langage
- **Multilingual-E5-Large** pour les embeddings multilingues
- **PostgreSQL + PGVector** pour le stockage vectoriel
- **FastAPI** pour le serveur d'embeddings

**✅ Zéro dépendance OpenAI** | **🇫🇷 Optimisé français** | **🐳 Déployable sur Coolify**

---

## 🎯 Caractéristiques

- 💬 **CLI interactive** avec streaming des réponses
- 🔍 **Recherche sémantique** dans vos documents
- 📚 **Support multi-formats** : PDF, Word, PowerPoint, Markdown, etc. (via Docling)
- 🎯 **Citations des sources** pour toutes les réponses
- 🇫🇷 **Performance française** avec Chocolatine-2-14B (équivalent GPT-4o-mini)
- 💾 **Base vectorielle** PostgreSQL + PGVector scalable
- 🧠 **Embeddings locaux** avec multilingual-e5-large (1024 dim)
- 🐳 **Déploiement simple** via Docker Compose ou Coolify

---

## 📋 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   COOLIFY / DOCKER                      │
│                                                         │
│  ┌──────────────────┐      ┌──────────────────┐       │
│  │ Embeddings API   │      │ PostgreSQL       │       │
│  │ (E5-Large)       │◄────►│ + PGVector       │       │
│  │ Port: 8001       │      │ Port: 5432       │       │
│  └────────┬─────────┘      └────────┬─────────┘       │
│           │                         │                  │
│           └─────────┬───────────────┘                  │
│                     │                                  │
│           ┌─────────▼─────────┐                        │
│           │   RAG App (CLI)   │                        │
│           └─────────┬─────────┘                        │
└─────────────────────┼─────────────────────────────────┘
                      │
                      ▼
           ┌──────────────────────┐
           │ API LLM Chocolatine  │
           │ apigpt.mynumih.fr    │
           └──────────────────────┘
```

---

## 🚀 Installation Rapide

### Option 1 : Docker Compose (Recommandé)

```bash
# 1. Cloner le repo
git clone https://github.com/famatulli1/ragfab.git
cd ragfab

# 2. Configurer l'environnement
cp .env.example .env
# Éditer .env avec vos valeurs (notamment CHOCOLATINE_API_URL)

# 3. Démarrer les services
docker-compose up -d

# 4. Vérifier que tout fonctionne
docker-compose ps
docker-compose logs embeddings  # Vérifier le chargement du modèle
```

### Option 2 : Déploiement Coolify

1. **Créer un nouveau projet** dans Coolify
2. **Connecter le repo GitHub** : `https://github.com/famatulli1/ragfab`
3. **Sélectionner** `docker-compose.coolify.yml`
4. **Configurer les variables d'environnement** (voir `.env.example`)
5. **Déployer** 🚀

Les services PostgreSQL et Embeddings seront automatiquement déployés et accessibles.

---

## ⚙️ Configuration

### Variables d'environnement essentielles

Créez un fichier `.env` à partir de `.env.example` :

```bash
# Base de données PostgreSQL
DATABASE_URL=postgresql://raguser:votremotdepasse@postgres:5432/ragdb

# Serveur d'embeddings
EMBEDDINGS_API_URL=http://embeddings:8001
EMBEDDING_DIMENSION=1024

# API LLM Chocolatine
CHOCOLATINE_API_URL=https://apigpt.mynumih.fr
CHOCOLATINE_API_KEY=  # Si nécessaire
```

### Pour Coolify :
- Remplacez `postgres` par `postgres.internal` ou le nom du service
- Remplacez `embeddings:8001` par l'URL exposée par Coolify
- Configurez les variables via l'interface Coolify

---

## 📚 Utilisation

### 1. Ingestion de documents

Placez vos documents dans `rag-app/documents/` puis :

```bash
# Avec Docker
docker-compose run --rm rag-app python -m ingestion.ingest --documents /app/documents

# En local (après installation des dépendances)
cd rag-app
python -m ingestion.ingest --documents documents/
```

**Formats supportés** :
- 📄 PDF (`.pdf`)
- 📝 Word (`.docx`, `.doc`)
- 📊 PowerPoint (`.pptx`)
- 📋 Markdown (`.md`)
- 📃 Texte (`.txt`)
- Et plus via Docling...

### 2. Lancer l'agent RAG

```bash
# Avec Docker
docker-compose --profile app up rag-app

# En local
cd rag-app
python rag_agent.py
```

Exemple de session :

```
============================================================
🤖 Assistant RAG de Connaissances (Chocolatine-2-14B)
============================================================
Posez-moi des questions sur la base de connaissances!
Tapez 'quit', 'exit', ou Ctrl+C pour quitter.
============================================================

Vous: Quels sont les principaux sujets abordés dans la documentation ?
Assistant: D'après la base de connaissances, voici les principaux sujets...

[Réponse avec citations des sources]

Vous: quit
Assistant: Merci d'avoir utilisé l'assistant. Au revoir!
```

---

## 🗄️ Schéma de Base de Données

Le schéma PostgreSQL est automatiquement créé au démarrage :

```sql
-- Table des documents sources
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Table des chunks avec embeddings (1024 dimensions)
CREATE TABLE chunks (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES documents(id),
    content TEXT NOT NULL,
    embedding vector(1024),  -- multilingual-e5-large
    chunk_index INTEGER,
    metadata JSONB,
    token_count INTEGER,
    created_at TIMESTAMP
);

-- Fonction de recherche par similarité
CREATE FUNCTION match_chunks(
    query_embedding vector(1024),
    match_count INT DEFAULT 10,
    similarity_threshold FLOAT DEFAULT 0.0
) RETURNS TABLE (...);
```

---

## 🛠️ Développement Local

### Prérequis

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 15+ avec PGVector (ou via Docker)

### Installation

```bash
# 1. Cloner le repo
git clone https://github.com/famatulli1/ragfab.git
cd ragfab

# 2. Installer les dépendances du serveur d'embeddings
cd embeddings-server
pip install -r requirements.txt

# 3. Installer les dépendances de l'app RAG
cd ../rag-app
pip install -r requirements.txt

# 4. Configurer l'environnement
cp ../.env.example ../.env
# Éditer .env
```

### Lancer en local (sans Docker)

```bash
# Terminal 1 : PostgreSQL (via Docker)
docker run -d \
  --name ragfab-postgres \
  -e POSTGRES_USER=raguser \
  -e POSTGRES_PASSWORD=ragpass123 \
  -e POSTGRES_DB=ragdb \
  -p 5432:5432 \
  -v $(pwd)/database/schema.sql:/docker-entrypoint-initdb.d/schema.sql \
  pgvector/pgvector:pg16

# Terminal 2 : Serveur d'embeddings
cd embeddings-server
python app.py

# Terminal 3 : Application RAG
cd rag-app
export DATABASE_URL=postgresql://raguser:ragpass123@localhost:5432/ragdb
export EMBEDDINGS_API_URL=http://localhost:8001
export CHOCOLATINE_API_URL=https://apigpt.mynumih.fr
python rag_agent.py
```

---

## 🧪 Tests

### Tester le serveur d'embeddings

```bash
curl -X POST http://localhost:8001/embed \
  -H "Content-Type: application/json" \
  -d '{"text": "Bonjour, ceci est un test"}'

# Réponse attendue :
# {
#   "embedding": [0.123, -0.456, ...],  # 1024 valeurs
#   "dimension": 1024,
#   "model": "intfloat/multilingual-e5-large"
# }
```

### Tester la base de données

```bash
# Se connecter à PostgreSQL
docker exec -it ragfab-postgres psql -U raguser -d ragdb

# Vérifier les tables
\dt

# Vérifier l'extension PGVector
\dx

# Compter les documents
SELECT COUNT(*) FROM documents;
SELECT COUNT(*) FROM chunks;
```

---

## 📊 Performance et Ressources

### Serveur d'embeddings
- **CPU** : 2-4 cores recommandés
- **RAM** : 4-8 GB recommandés
- **Latence** :
  - Embedding unique : ~50-200ms
  - Batch de 100 : ~2-5s

### PostgreSQL
- **CPU** : 1-2 cores
- **RAM** : 2-4 GB
- **Stockage** : Dépend du nombre de documents

### Application RAG
- **CPU** : 1-2 cores
- **RAM** : 1-2 GB
- **Requêtes** : Dépendent de votre API Chocolatine

**Total recommandé** : 6-8 cores, 8-12 GB RAM

---

## 🔧 Personnalisation

### Changer le modèle d'embeddings

Modifiez dans `.env` :

```bash
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-mpnet-base-v2
EMBEDDING_DIMENSION=768  # Attention à la dimension !
```

⚠️ **Important** : Si vous changez de dimension, vous devez :
1. Modifier `database/schema.sql` : `vector(1024)` → `vector(768)`
2. Recréer la base de données

### Personnaliser le chunking

Dans `.env` :

```bash
CHUNK_SIZE=1500              # Chunks plus grands
CHUNK_OVERLAP=300            # Plus de chevauchement
USE_SEMANTIC_CHUNKING=true   # Chunking intelligent
```

### Modifier le prompt système

Éditez `rag-app/rag_agent.py` dans la création de l'agent :

```python
agent = Agent(
    chocolatine_model,
    system_prompt="""Votre prompt personnalisé ici...""",
    tools=[search_knowledge_base],
)
```

---

## 🐛 Dépannage

### Le serveur d'embeddings ne démarre pas

```bash
# Vérifier les logs
docker-compose logs embeddings

# Le modèle est volumineux (~2.2GB), le premier démarrage peut prendre 2-5 minutes
# Vérifier l'espace disque disponible
```

### Erreur de connexion à PostgreSQL

```bash
# Vérifier que PostgreSQL est démarré
docker-compose ps postgres

# Vérifier les logs
docker-compose logs postgres

# Tester la connexion
docker exec -it ragfab-postgres psql -U raguser -d ragdb
```

### Erreur "Modèle Chocolatine non accessible"

```bash
# Vérifier que votre API est accessible
curl https://apigpt.mynumih.fr/health  # ou votre endpoint

# Vérifier CHOCOLATINE_API_URL dans .env
```

### Dimension d'embedding incorrecte

```bash
# Vérifier la dimension du modèle
curl http://localhost:8001/info

# Vérifier que EMBEDDING_DIMENSION correspond dans .env
# Vérifier que schema.sql utilise la bonne dimension
```

---

## 📖 Documentation Technique

### API Serveur d'Embeddings

**Endpoint** : `/embed`
```bash
POST /embed
Content-Type: application/json

{
  "text": "Votre texte ici"
}

# Réponse :
{
  "embedding": [0.123, ...],
  "dimension": 1024,
  "model": "intfloat/multilingual-e5-large"
}
```

**Endpoint** : `/embed_batch`
```bash
POST /embed_batch
Content-Type: application/json

{
  "texts": ["Texte 1", "Texte 2", ...]
}

# Réponse :
{
  "embeddings": [[0.123, ...], [0.456, ...]],
  "count": 2,
  "dimension": 1024,
  "model": "intfloat/multilingual-e5-large"
}
```

### Structure du Projet

```
ragfab/
├── embeddings-server/          # Serveur d'embeddings FastAPI
│   ├── app.py                  # Application FastAPI
│   ├── Dockerfile
│   └── requirements.txt
├── rag-app/                    # Application RAG principale
│   ├── ingestion/              # Pipeline d'ingestion
│   │   ├── ingest.py
│   │   ├── embedder.py        # Client embeddings
│   │   └── chunker.py
│   ├── utils/
│   │   ├── chocolatine_provider.py  # Provider LLM
│   │   ├── db_utils.py
│   │   └── models.py
│   ├── rag_agent.py           # Agent RAG principal
│   ├── cli.py                 # CLI amélioré
│   ├── Dockerfile
│   └── requirements.txt
├── database/                   # Configuration PostgreSQL
│   ├── schema.sql             # Schéma avec PGVector
│   └── init.sh
├── docker-compose.yml         # Dev/Local
├── docker-compose.coolify.yml # Production Coolify
├── .env.example
└── README.md
```

---

## 🤝 Contribution

Les contributions sont les bienvenues ! Pour contribuer :

1. Fork le projet
2. Créez une branche (`git checkout -b feature/amelioration`)
3. Committez vos changements (`git commit -m 'Ajout fonctionnalité'`)
4. Push vers la branche (`git push origin feature/amelioration`)
5. Ouvrez une Pull Request

---

## 📝 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

---

## 🙏 Remerciements

- **Chocolatine-2-14B** par [@jpacifico](https://huggingface.co/jpacifico)
- **Multilingual-E5** par Microsoft
- **PGVector** pour l'extension PostgreSQL
- **Docling** pour le traitement de documents
- **PydanticAI** pour le framework d'agents

---

## 📧 Contact

Pour toute question ou support :
- Ouvrir une issue sur GitHub
- Contribuer via Pull Request

---

**Fait avec ❤️ pour la communauté française de l'IA**

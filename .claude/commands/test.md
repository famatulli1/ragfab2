# Commande /test - Exécution des Tests RAGFab

Tu es un expert en testing Python et React. Exécute les tests du projet RAGFab.

## Structure des Tests

```
rag-app/tests/          # Tests backend ingestion
web-api/tests/          # Tests API FastAPI
frontend/               # Tests React (npm test)
```

## Actions Disponibles

### 1. Tests Backend (rag-app)

```bash
cd rag-app
pytest -m unit -v                           # Tests unitaires uniquement
pytest -m "unit and not embeddings" -v      # Exclure tests embeddings (lents)
pytest --cov=. --cov-report=term            # Avec couverture
```

### 2. Tests API (web-api)

```bash
cd web-api
pytest -m unit -v                           # Tests unitaires
pytest --cov=app --cov-report=term          # Avec couverture
```

### 3. Tests Frontend

```bash
cd frontend
npm test                                    # Tests React
npm run lint                                # ESLint
```

### 4. Tous les Tests

```bash
# Backend + API
cd rag-app && pytest -m unit && cd ../web-api && pytest -m unit

# Ou via Docker
docker-compose exec ragfab-api pytest -m unit
```

## Paramètres

- **--cov** : Génère rapport de couverture
- **-m unit** : Uniquement tests marqués @pytest.mark.unit
- **-v** : Mode verbose
- **-x** : Stop au premier échec

## Seuil de Couverture

- **Actuel** : 20% (baseline réaliste)
- **Objectif** : Augmenter progressivement

## Exécuter

Quel type de tests souhaitez-vous exécuter ?
1. **unit** - Tests unitaires rapides
2. **api** - Tests API FastAPI
3. **frontend** - Tests React + lint
4. **all** - Tous les tests
5. **coverage** - Tests avec rapport de couverture

# Pipeline RAG de RAGFab : Guide Complet pour Non-Techniques

## 📚 Qu'est-ce qu'un système RAG ?

**RAG** signifie "Retrieval Augmented Generation" (Génération Augmentée par Récupération).

Imaginez que vous avez une bibliothèque immense avec des milliers de livres. Quand quelqu'un vous pose une question, vous devez :
1. **Trouver les bons livres** qui contiennent l'information
2. **Lire les passages pertinents**
3. **Formuler une réponse** basée sur ce que vous avez lu

C'est exactement ce que fait notre système RAGFab, mais avec des documents PDF et une intelligence artificielle !

---

## 🔄 Vue d'ensemble de la pipeline

Notre système fonctionne en **deux grandes phases** :

### Phase 1 : L'Ingestion (Préparation des documents)
C'est comme organiser une bibliothèque : on range les livres, on crée un index, on prépare tout pour pouvoir retrouver l'information rapidement.

### Phase 2 : La Restitution (Répondre aux questions)
C'est comme aider un visiteur à la bibliothèque : on cherche les bons documents, on lit les passages pertinents, on formule une réponse claire.

---

## 📥 PHASE 1 : L'INGESTION DES DOCUMENTS

### Étape 1 : La Conversion (Docling)

**Objectif** : Transformer les PDF en texte structuré compréhensible par l'ordinateur.

**Module concerné** : `rag-app/ingestion/converter.py`

**Ce qui se passe** :
- Nous utilisons **Docling**, un outil spécialisé qui comprend la structure des documents
- Docling ne lit pas simplement le texte comme un scanner, il **comprend** :
  - Les titres et sous-titres
  - Les paragraphes
  - Les tableaux
  - Les listes
  - La mise en page

**Exemple concret** :
```
Document PDF original :
┌─────────────────────┐
│ TITRE : Les Énergies │
│                     │
│ Introduction        │
│ Le solaire est...   │
│                     │
│ Types d'énergies    │
│ 1. Solaire          │
│ 2. Éolienne         │
└─────────────────────┘

Après Docling :
{
  "type": "heading",
  "text": "Les Énergies",
  "level": 1
}
{
  "type": "heading",
  "text": "Introduction",
  "level": 2
}
{
  "type": "paragraph",
  "text": "Le solaire est..."
}
...
```

**Pourquoi c'est important ?**
- Un PDF peut contenir du texte en colonnes, des images, des tableaux complexes
- Docling comprend tout ça et l'organise intelligemment
- Nous obtenons un document structuré, pas juste un bloc de texte

---

### Étape 2 : Le Découpage (Chunking)

**Objectif** : Découper le long document en petits morceaux digestes.

**Module concerné** : `rag-app/ingestion/chunker.py`

**Pourquoi découper ?**

Imaginez que quelqu'un vous demande "Quelle est la capitale de la France ?". Vous n'avez pas besoin de lui lire un livre entier sur la géographie française, juste la phrase : "La capitale de la France est Paris."

C'est pareil pour notre IA : on découpe les documents en **chunks** (morceaux) de taille raisonnable.

**Notre stratégie de découpage** :

Nous utilisons **HybridChunker** de Docling qui est intelligent :

1. **Il respecte la structure du document** :
   - Il ne coupe pas un paragraphe en plein milieu
   - Il garde les titres avec leur contenu
   - Il préserve l'intégrité des tableaux

2. **Configuration** :
   - Taille idéale d'un chunk : **1500 caractères** (environ 250 mots)
   - Chevauchement entre chunks : **200 caractères**

**Pourquoi le chevauchement ?**

Imaginez ce texte :
```
Chunk 1 : "Le solaire photovoltaïque transforme..."
Chunk 2 : "...la lumière en électricité. Cette technologie..."
```

Sans chevauchement, si quelqu'un cherche "transformation de la lumière en électricité", il pourrait rater l'information car elle est coupée entre deux chunks.

Avec chevauchement de 200 caractères :
```
Chunk 1 : "Le solaire photovoltaïque transforme la lumière en électricité. Cette..."
Chunk 2 : "...la lumière en électricité. Cette technologie utilise..."
```

Maintenant, les deux chunks contiennent la phrase complète !

**Fallback (plan B)** :

Si HybridChunker échoue (document trop complexe), on utilise **SimpleChunker** :
- Découpe le texte aux doubles sauts de ligne (`\n\n`)
- Respecte les paragraphes naturels
- Moins intelligent mais très fiable

---

### Étape 3 : La Transformation en Nombres (Embeddings)

**Objectif** : Convertir le texte en "empreinte numérique" pour permettre la recherche.

**Module concerné** : `rag-app/ingestion/embedder.py`

**Le concept d'embedding expliqué simplement** :

Imaginez que vous voulez organiser des livres dans une bibliothèque. Vous pourriez :
- Les classer par ordre alphabétique (pas très utile pour chercher par thème)
- Les classer par sujet (mieux !)
- Les placer sur une carte géographique imaginaire où les livres similaires sont proches

Les **embeddings**, c'est la troisième option ! On transforme chaque chunk de texte en **un point dans un espace à 1024 dimensions**.

**Comment ça marche ?**

1. On envoie le texte au service d'embeddings (modèle **E5-Large multilingue**)
2. Le modèle analyse le **sens** du texte (pas juste les mots)
3. Il retourne un vecteur de **1024 nombres** (dimensions)

**Exemple simplifié** :

```
Texte : "Le solaire photovoltaïque produit de l'électricité"

Embedding (simplifié à 5 dimensions pour l'exemple) :
[0.82, 0.34, 0.91, 0.12, 0.67]

Texte similaire : "Les panneaux solaires génèrent du courant"
[0.79, 0.31, 0.88, 0.15, 0.65]

Texte différent : "La cuisine française est renommée"
[0.12, 0.87, 0.23, 0.91, 0.34]
```

Regardez : les deux premiers textes (sur le solaire) ont des nombres similaires, le troisième (sur la cuisine) est très différent !

**Optimisation des performances** :

- On ne traite pas les chunks un par un (trop lent !)
- On les envoie par **lots de 20 chunks** au service d'embeddings
- Timeout de 90 secondes par lot pour éviter les erreurs

**Nettoyage UTF-8** :

Les PDF peuvent contenir des caractères bizarres (symboles spéciaux, emojis mal encodés). On nettoie tout ça avant de créer les embeddings :

```python
clean_content = content.encode('utf-8', errors='replace').decode('utf-8')
```

---

### Étape 4 : Le Stockage (Base de données PostgreSQL + PGVector)

**Objectif** : Sauvegarder tous les chunks et leurs embeddings pour pouvoir les retrouver rapidement.

**Modules concernés** : `rag-app/database/schema.sql`, `rag-app/database/db.py`

**Structure de la base de données** :

Nous avons **deux tables principales** :

#### Table `documents` :
C'est la fiche d'identité de chaque document PDF.

```
┌────────────────────────────────────────┐
│ ID │ Titre        │ Chemin        │ Date │
├────┼──────────────┼───────────────┼──────┤
│ 1  │ Énergies.pdf │ /docs/ener... │ 2024 │
│ 2  │ Climat.pdf   │ /docs/clim... │ 2024 │
└────────────────────────────────────────┘
```

#### Table `chunks` :
C'est chaque morceau de texte découpé, avec son embedding.

```
┌────────────────────────────────────────────────────────────┐
│ ID │ Doc │ Texte             │ Embedding (1024 dimensions) │
├────┼─────┼───────────────────┼─────────────────────────────┤
│ 1  │ 1   │ "Le solaire..."   │ [0.82, 0.34, 0.91, ...]    │
│ 2  │ 1   │ "Les panneaux..." │ [0.79, 0.31, 0.88, ...]    │
│ 3  │ 2   │ "Le climat..."    │ [0.12, 0.87, 0.23, ...]    │
└────────────────────────────────────────────────────────────┘
```

**PGVector : l'extension magique** :

PostgreSQL normalement ne peut pas chercher dans des vecteurs de nombres. Mais avec **PGVector**, on peut :
- Stocker des vecteurs de 1024 dimensions
- Chercher les vecteurs **les plus similaires** très rapidement
- Utiliser l'index **HNSW** (Hierarchical Navigable Small World) pour accélérer la recherche

C'est comme avoir un GPS dans notre bibliothèque de 1024 dimensions !

**Index HNSW** :

Au lieu de comparer notre question avec TOUS les chunks (lent), l'index HNSW crée une "carte routière" qui permet de trouver rapidement les chunks proches.

---

## 🔍 PHASE 2 : LA RESTITUTION (Répondre aux questions)

### Étape 1 : Reformulation de la Question (Optionnel mais intelligent)

**Objectif** : Comprendre les questions qui font référence à la conversation précédente.

**Module concerné** : `web-api/app/main.py` (fonction `reformulate_question_with_context`)

**Le problème des références contextuelles** :

Imaginez cette conversation :

```
Utilisateur : "Quelles sont les énergies renouvelables ?"
Assistant : "Les énergies renouvelables incluent le solaire, l'éolien..."

Utilisateur : "Et celle qui utilise l'eau ?"
```

La question "Et celle qui utilise l'eau ?" n'a AUCUN sens sans le contexte !

**Notre solution** :

On détecte automatiquement les références :
- **Pronoms démonstratifs** : celle, celui, celles, ceux (toujours reformulés)
- **Pronoms courts** : ça, cela, ce, cette, ces (si question courte < 8 mots)
- **Pronoms en début de phrase** : il, elle, ils, elles, y, en (si premier mot)
- **Patterns spéciaux** : "et celle", "et celui", "et ça"

Puis on demande à l'IA Mistral de reformuler :

```
Question originale : "Et celle qui utilise l'eau ?"
Historique récent : ["Quelles sont les énergies renouvelables ?", "Les énergies renouvelables incluent..."]

Question reformulée : "Quelle est l'énergie renouvelable qui utilise l'eau ?"
```

**Important** : On ne reformule PAS les articles génériques ("le", "la", "les") pour éviter les fausses détections.

---

### Étape 2 : Transformation de la Question en Embedding

**Objectif** : Convertir la question en vecteur de nombres pour la comparer aux chunks.

**Module concerné** : `web-api/app/tools.py` (fonction `search_knowledge_base_tool`)

On fait exactement la même chose qu'à l'ingestion :

```
Question : "Comment fonctionne l'énergie solaire ?"

Embedding de la question :
[0.80, 0.32, 0.89, 0.13, 0.66, ...]  (1024 nombres)
```

---

### Étape 3 : Recherche par Similarité (Vector Search)

**Objectif** : Trouver les chunks les plus pertinents pour répondre à la question.

**Module concerné** : `web-api/app/tools.py` (fonction `search_knowledge_base_tool`)

**Comment ça marche ?**

1. On a l'embedding de la question : `[0.80, 0.32, 0.89, ...]`
2. On compare avec TOUS les embeddings des chunks dans la base
3. On utilise la **distance cosinus** pour mesurer la similarité

**Distance cosinus expliquée** :

Imaginez deux flèches dans l'espace :
- Si elles pointent dans la même direction → angle petit → **très similaires**
- Si elles pointent dans des directions opposées → angle grand → **très différentes**

```
Question embedding : ────────►
Chunk similaire :    ────────►  (angle petit = 0.95 de similarité)
Chunk différent :    ↑          (angle grand = 0.32 de similarité)
```

**Requête SQL magique** :

```sql
SELECT
  c.content,
  d.title,
  1 - (c.embedding <=> $1) AS similarity
FROM chunks c
JOIN documents d ON c.document_id = d.id
ORDER BY c.embedding <=> $1
LIMIT 5
```

Traduction :
- `<=>` = opérateur de distance cosinus de PGVector
- `1 - distance` = similarité (plus proche de 1 = plus similaire)
- `ORDER BY` = trier du plus similaire au moins similaire
- `LIMIT 5` = retourner les 5 meilleurs résultats

**Résultat** :

```
Top 5 chunks pertinents :
1. "Le solaire photovoltaïque transforme..." (similarité: 0.92)
2. "Les panneaux solaires contiennent..."    (similarité: 0.89)
3. "L'énergie solaire est renouvelable..."   (similarité: 0.85)
4. "Le photovoltaïque utilise l'effet..."    (similarité: 0.83)
5. "Les cellules photovoltaïques sont..."    (similarité: 0.81)
```

**Stockage des sources** :

On sauvegarde ces chunks dans une **variable globale** `_current_request_sources` pour les afficher plus tard à l'utilisateur.

**Pourquoi une variable globale ?**

Normalement, on préférerait utiliser un système plus élégant (ContextVar), mais PydanticAI (le framework qu'on utilise pour l'IA) perd le contexte entre les appels. La variable globale fonctionne car FastAPI traite les requêtes une par une.

---

### Étape 4 : Génération de la Réponse (LLM)

**Objectif** : Utiliser une IA pour formuler une réponse basée sur les chunks trouvés.

**Module concerné** : `web-api/app/main.py` (fonction `execute_rag_agent`)

**Nous avons DEUX modes** :

#### Mode 1 : Mistral avec Tools (Recommandé)

**Comment ça marche ?**

1. On donne à l'IA Mistral un **outil** (function calling) : `search_knowledge_base_tool`
2. L'IA décide automatiquement d'utiliser l'outil pour chercher l'information
3. L'outil retourne les chunks pertinents
4. L'IA génère une réponse basée sur ces chunks

**Flow détaillé** :

```
┌─────────────────────────────────────────────────────┐
│ 1. User Question                                    │
│    "Comment fonctionne l'énergie solaire ?"         │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│ 2. Reformulation (si nécessaire)                    │
│    Question reformulée ou originale                 │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│ 3. Agent Mistral créé AVEC l'outil                  │
│    tools = [search_knowledge_base_tool]             │
│    message_history = []  (vide pour forcer l'outil) │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│ 4. Mistral décide d'appeler l'outil                 │
│    "Je vais chercher des infos sur le solaire"      │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│ 5. Outil exécuté : Vector Search                    │
│    - Embedding de la question                       │
│    - Recherche des 5 chunks similaires              │
│    - Sauvegarde dans _current_request_sources       │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│ 6. Mistral reçoit les chunks                        │
│    "Voici les informations trouvées : ..."          │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│ 7. Mistral génère la réponse finale                 │
│    "L'énergie solaire photovoltaïque fonctionne..." │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│ 8. Réponse + Sources envoyées à l'utilisateur       │
│    - Texte de réponse                               │
│    - Liste des 5 sources (titre, contenu, page)     │
└─────────────────────────────────────────────────────┘
```

**Particularité importante** :

On passe `message_history=[]` (historique vide) pour **forcer** Mistral à appeler l'outil à chaque fois. Sinon, Mistral pourrait répondre directement depuis l'historique de conversation sans chercher dans la base !

#### Mode 2 : Chocolatine OU Mistral sans Tools

**Comment ça marche ?**

1. On exécute MANUELLEMENT la recherche vector
2. On récupère les chunks pertinents
3. On les **injecte directement** dans le prompt système de l'IA
4. L'IA génère une réponse basée sur ce contexte

**Flow simplifié** :

```
Question → Vector Search → Injection dans prompt → Réponse
```

**Exemple de prompt** :

```
SYSTÈME: Tu es un assistant qui répond en français basé sur ces documents :

DOCUMENT 1:
Le solaire photovoltaïque transforme la lumière en électricité...

DOCUMENT 2:
Les panneaux solaires contiennent des cellules photovoltaïques...

UTILISATEUR: Comment fonctionne l'énergie solaire ?

ASSISTANT: [génère une réponse basée sur les documents fournis]
```

**Avantage** : Plus simple, fonctionne avec n'importe quel LLM
**Inconvénient** : Moins flexible, l'IA ne peut pas décider de chercher plus d'infos

---

### Étape 5 : Affichage des Sources

**Objectif** : Montrer à l'utilisateur d'où viennent les informations (transparence).

**Module concerné** : `frontend/src/components/SourcesList.tsx`

**Ce qui est affiché** :

Pour chaque source (chunk) utilisée :
- 📄 **Titre du document** (ex: "Guide_Energies_Renouvelables.pdf")
- 📝 **Extrait du texte** (les 200 premiers caractères du chunk)
- 📍 **Position** dans le document (numéro du chunk)
- 🔗 **Lien pour voir le document complet** (si disponible)

**Exemple visuel** :

```
┌──────────────────────────────────────────────────┐
│ Sources utilisées pour cette réponse :           │
│                                                  │
│ [1] 📄 Guide_Energies_Renouvelables.pdf          │
│     "Le solaire photovoltaïque transforme la     │
│      lumière du soleil en électricité grâce..."  │
│     📍 Chunk 12 | 🔗 Voir le document            │
│                                                  │
│ [2] 📄 Rapport_Transition_Energetique.pdf        │
│     "Les panneaux solaires sont composés de..."  │
│     📍 Chunk 8 | 🔗 Voir le document             │
└──────────────────────────────────────────────────┘
```

**Pourquoi c'est important ?**

- **Transparence** : L'utilisateur sait que la réponse vient de documents réels
- **Vérifiabilité** : L'utilisateur peut vérifier l'information dans le document source
- **Confiance** : L'IA ne "hallucine" pas, elle cite ses sources

---

## 🔧 Technologies Utilisées (Pour les Curieux)

### Infrastructure
- **Docker** : Conteneurisation de tous les services
- **PostgreSQL** : Base de données principale
- **PGVector** : Extension pour stocker et chercher dans les vecteurs

### Backend
- **FastAPI** : Framework web Python pour l'API
- **PydanticAI** : Framework pour orchestrer les agents IA
- **Docling** : Conversion et chunking intelligent des PDF
- **SQLAlchemy** : ORM pour interagir avec la base de données

### IA et Embeddings
- **Mistral AI** : LLM pour générer les réponses
- **E5-Large Multilingue** : Modèle d'embeddings (1024 dimensions)
- **sentence-transformers** : Bibliothèque pour générer les embeddings

### Frontend
- **React** : Framework JavaScript pour l'interface utilisateur
- **TypeScript** : JavaScript avec typage pour éviter les erreurs
- **TailwindCSS** : Framework CSS pour le design
- **Vite** : Build tool moderne et rapide

---

## 📊 Schéma Complet de la Pipeline

```
┌───────────────────────────────────────────────────────────────┐
│                    PHASE 1 : INGESTION                        │
└───────────────────────────────────────────────────────────────┘

Documents PDF
    │
    ▼
┌─────────────────┐
│ 1. CONVERSION   │  Docling lit et structure le PDF
│    (Docling)    │  → Titres, paragraphes, tableaux
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. CHUNKING     │  Découpe en morceaux de 1500 caractères
│  (HybridChunker)│  → Chunks avec chevauchement de 200
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 3. EMBEDDINGS   │  Transforme en vecteurs de 1024 nombres
│   (E5-Large)    │  → [0.82, 0.34, 0.91, ...]
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 4. STOCKAGE     │  Sauvegarde dans PostgreSQL + PGVector
│   (PostgreSQL)  │  → Table chunks avec index HNSW
└─────────────────┘

┌───────────────────────────────────────────────────────────────┐
│                  PHASE 2 : RESTITUTION                        │
└───────────────────────────────────────────────────────────────┘

Question utilisateur
    │
    ▼
┌──────────────────┐
│ 1. REFORMULATION │  Détecte les références contextuelles
│    (Optionnel)   │  → "Et celle-ci ?" → "Quelle est cette énergie ?"
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 2. EMBEDDING     │  Question → vecteur de 1024 nombres
│   (E5-Large)     │  → [0.80, 0.32, 0.89, ...]
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 3. VECTOR SEARCH │  Recherche par similarité cosinus
│   (PGVector)     │  → Top 5 chunks similaires
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 4. GÉNÉRATION    │  LLM génère la réponse avec contexte
│   (Mistral)      │  → Réponse basée sur les chunks trouvés
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 5. AFFICHAGE     │  Réponse + Sources affichées
│   (React)        │  → Transparence et vérifiabilité
└──────────────────┘
```

---

## 🎯 Points Clés à Retenir

### Pour l'Ingestion :
1. **Docling** comprend la structure des documents (pas juste du texte brut)
2. **HybridChunker** découpe intelligemment en respectant le sens
3. **Embeddings** transforment le texte en "empreinte numérique" (1024 dimensions)
4. **PGVector** stocke et permet de chercher rapidement parmi des millions de chunks

### Pour la Restitution :
1. **Reformulation** rend les questions contextuelles autonomes
2. **Vector Search** trouve les chunks similaires par distance cosinus
3. **Mistral avec Tools** appelle automatiquement la recherche
4. **Sources affichées** pour la transparence et la vérifiabilité

### Pourquoi c'est Puissant :
- ✅ Cherche par **sens**, pas par mots-clés
- ✅ Fonctionne même si la question utilise des mots différents
- ✅ Rapide : index HNSW optimisé
- ✅ Transparent : sources toujours affichées
- ✅ Multilingue : modèle E5-Large optimisé pour le français

---

## 🚀 Exemple Complet de Bout en Bout

### Ingestion du document "Guide_Energies_Renouvelables.pdf"

**1. Conversion (Docling)** :
```
PDF → Structure JSON
{
  "heading": "Les Énergies Renouvelables",
  "paragraph": "L'énergie solaire photovoltaïque transforme la lumière du soleil en électricité grâce à l'effet photovoltaïque. Les panneaux solaires sont composés de cellules de silicium qui génèrent un courant électrique lorsqu'elles sont exposées à la lumière..."
}
```

**2. Chunking (HybridChunker)** :
```
Chunk 12 (1342 caractères) :
"L'énergie solaire photovoltaïque transforme la lumière du soleil en électricité grâce à l'effet photovoltaïque. Les panneaux solaires sont composés de cellules de silicium qui génèrent un courant électrique lorsqu'elles sont exposées à la lumière. Cette technologie permet de produire de l'électricité de manière propre et renouvelable..."
```

**3. Embeddings (E5-Large)** :
```
Texte → Vecteur
[0.1523, 0.8234, 0.4521, ..., 0.6789] (1024 nombres au total)
```

**4. Stockage (PostgreSQL)** :
```sql
INSERT INTO chunks (document_id, content, embedding, chunk_index)
VALUES (1, 'L'énergie solaire photovoltaïque...', '[0.1523, 0.8234, ...]', 12);
```

### Réponse à la question "Comment l'énergie solaire produit de l'électricité ?"

**1. Reformulation** :
```
Pas de référence contextuelle détectée
→ Question conservée telle quelle
```

**2. Embedding de la question** :
```
"Comment l'énergie solaire produit de l'électricité ?"
→ [0.1498, 0.8201, 0.4489, ..., 0.6823]
```

**3. Vector Search** :
```sql
SELECT content, title,
       1 - (embedding <=> '[0.1498, 0.8201, ...]') AS similarity
FROM chunks c JOIN documents d ON c.document_id = d.id
ORDER BY embedding <=> '[0.1498, 0.8201, ...]'
LIMIT 5;
```

**Résultats** :
```
1. Chunk 12 de "Guide_Energies_Renouvelables.pdf" (similarité: 0.94)
   "L'énergie solaire photovoltaïque transforme la lumière..."

2. Chunk 15 de "Guide_Energies_Renouvelables.pdf" (similarité: 0.89)
   "Les cellules photovoltaïques sont fabriquées en silicium..."

3. Chunk 8 de "Rapport_Transition_Energetique.pdf" (similarité: 0.85)
   "Le photovoltaïque utilise l'effet photoélectrique découvert..."

[... 2 autres chunks ...]
```

**4. Génération avec Mistral** :

Mistral reçoit :
- La question reformulée
- Les 5 chunks pertinents
- L'instruction de répondre en français

Mistral génère :
```
"L'énergie solaire photovoltaïque produit de l'électricité en transformant
la lumière du soleil en courant électrique grâce à l'effet photovoltaïque.
Les panneaux solaires contiennent des cellules de silicium qui, lorsqu'elles
sont exposées à la lumière, génèrent un flux d'électrons créant ainsi un
courant électrique. Cette technologie permet de produire de l'électricité
de manière propre et renouvelable."
```

**5. Affichage** :

```
┌────────────────────────────────────────────────────────────┐
│ 🤖 Réponse :                                               │
│                                                            │
│ L'énergie solaire photovoltaïque produit de l'électricité  │
│ en transformant la lumière du soleil en courant            │
│ électrique grâce à l'effet photovoltaïque...               │
│                                                            │
├────────────────────────────────────────────────────────────┤
│ 📚 Sources utilisées :                                     │
│                                                            │
│ [1] 📄 Guide_Energies_Renouvelables.pdf                    │
│     "L'énergie solaire photovoltaïque transforme..."       │
│     📍 Chunk 12 | Similarité: 94% | 🔗 Voir               │
│                                                            │
│ [2] 📄 Guide_Energies_Renouvelables.pdf                    │
│     "Les cellules photovoltaïques sont fabriquées..."      │
│     📍 Chunk 15 | Similarité: 89% | 🔗 Voir               │
│                                                            │
│ [3] 📄 Rapport_Transition_Energetique.pdf                  │
│     "Le photovoltaïque utilise l'effet photoélectrique..." │
│     📍 Chunk 8 | Similarité: 85% | 🔗 Voir                │
└────────────────────────────────────────────────────────────┘
```

---

## 🎓 Glossaire des Termes Techniques

- **RAG** : Retrieval Augmented Generation - Système qui cherche des informations dans une base de documents pour améliorer les réponses d'une IA

- **Chunk** : Morceau de texte découpé (généralement 1500 caractères dans notre cas)

- **Embedding** : Représentation numérique d'un texte sous forme de vecteur (1024 nombres)

- **Vector Search** : Recherche qui compare des vecteurs pour trouver les plus similaires

- **Distance Cosinus** : Mesure de similarité entre deux vecteurs (0 = très différent, 1 = identique)

- **PGVector** : Extension PostgreSQL pour stocker et chercher dans des vecteurs

- **HNSW** : Index optimisé pour accélérer la recherche dans les vecteurs

- **LLM** : Large Language Model - Grand modèle de langage (IA comme Mistral, GPT, etc.)

- **Function Calling / Tools** : Capacité d'une IA à utiliser des outils externes (comme notre recherche vector)

- **Token** : Unité de texte pour l'IA (environ 0.75 mots en français)

---

## 📞 Questions Fréquentes

**Q : Pourquoi 1024 dimensions pour les embeddings ?**
R : C'est la taille du modèle E5-Large. Plus il y a de dimensions, plus la représentation est précise, mais plus ça prend de place en mémoire. 1024 est un bon compromis.

**Q : Pourquoi découper en chunks de 1500 caractères ?**
R : C'est un équilibre entre :
- Trop petit → perd le contexte
- Trop grand → moins précis pour la recherche
1500 caractères = environ 2-3 paragraphes, c'est idéal.

**Q : Que se passe-t-il si aucun chunk n'est similaire à la question ?**
R : Le système retourne quand même les 5 "meilleurs" chunks (les moins pires). L'IA peut alors dire "Je n'ai pas trouvé d'information pertinente dans les documents".

**Q : Peut-on ajouter des documents sans tout ré-ingérer ?**
R : Oui ! Chaque document est ingéré indépendamment. On peut ajouter de nouveaux PDFs sans toucher aux anciens.

**Q : Pourquoi Mistral et pas GPT-4 ?**
R : Mistral est excellent pour le français, open-source, et moins cher. On peut aussi facilement changer de modèle grâce à l'architecture modulaire.

---

**Ce document a été créé pour expliquer la pipeline RAG de RAGFab de manière accessible à un public non technique.**

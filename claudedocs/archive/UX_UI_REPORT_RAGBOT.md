# Rapport UX/UI - RAGBot (ragbot.lab-numihfrance.fr)

**Date**: 10 octobre 2025
**Site testé**: https://ragbot.lab-numihfrance.fr
**Utilisateur de test**: toto (fabrice toto)

---

## 🎯 Résumé Exécutif

RAGBot présente une interface soignée et professionnelle pour un chatbot RAG (Retrieval Augmented Generation) destiné à un usage technique/médical. L'expérience utilisateur est **globalement positive** avec une interface moderne et intuitive, bien que certains aspects puissent être améliorés.

**Score global estimé**: 7.5/10

---

## ✅ Points Forts

### 1. Design Visuel
- **Interface épurée et moderne**: Design sombre élégant avec des accents bleu/cyan cohérents
- **Thème clair/sombre**: Implémentation réussie du toggle dark/light mode
- **Typographie lisible**: Hiérarchie claire, bon contraste texte/fond
- **Icônes cohérentes**: Utilisation cohérente d'icônes Lucide React

### 2. Architecture de l'Information
- **Sidebar fonctionnelle**: Historique des conversations accessible et bien organisé
- **Structure conversationnelle claire**: Messages utilisateur/bot bien différenciés visuellement
- **Affichage des sources**: Système de traçabilité excellent avec:
  - Noms de documents cliquables
  - Pourcentages de similarité visibles (ex: 88.1%)
  - Numéros de chunks pour référence
  - Prévisualisation du contenu du chunk

### 3. Fonctionnalités Avancées
- **Visualisation de documents**: Modal overlay avec contenu complet du document
- **Highlight des chunks utilisés**: Badge jaune pour identifier le chunk exact utilisé dans la réponse
- **Export Markdown**: Fonctionnalité pratique pour sauvegarder les conversations
- **Feedback utilisateur**: Boutons "Bon/Mauvais" pour évaluer les réponses
- **Reranking toggle**: Option avancée accessible pour optimiser les résultats
- **Avatar personnalisé**: Initiale de l'utilisateur dans un cercle coloré (vert)

### 4. État du Système
- **Indicateurs de statut clairs**: Badge "4 messages" sur les conversations
- **Gestion multi-conversations**: Possibilité de créer plusieurs conversations parallèles

---

## ⚠️ Points à Améliorer

### 1. Navigation et Interactions

**Problème: Sidebar cachée sur mobile**
- Sur viewport étroit, la sidebar disparaît derrière un bouton hamburger
- Le bouton "Nouvelle conversation" devient difficile d'accès
- **Solution**: Améliorer la gestion responsive de la sidebar (slide-in overlay)

**Problème: Menu utilisateur peu visible**
- Le menu dropdown utilisateur est discret (petit avatar en haut à droite)
- Pas d'indication visuelle qu'il s'agit d'un menu cliquable
- **Solution**: Ajouter un chevron ou un hover effect plus marqué

### 2. Affordances et Feedback

**Problème: Boutons désactivés peu explicites**
- Le bouton d'envoi de message est désactivé (grisé) quand le champ est vide
- Aucun tooltip n'explique pourquoi
- **Solution**: Ajouter un tooltip "Tapez un message pour envoyer"

**Problème: États de chargement**
- Pas observé de loader/spinner pendant la génération de réponse
- L'utilisateur peut ne pas savoir si le système traite sa demande
- **Solution**: Ajouter un indicateur de chargement (typing indicator, spinner)

**Problème: Toggle Reranking sans explication**
- Le toggle "Reranking" n'a pas de tooltip explicatif
- Utilisateur non-technique peut ne pas comprendre son utilité
- **Solution**: Ajouter une info-bulle expliquant les bénéfices du reranking

### 3. Accessibilité

**Problème: Contraste des chunks de sources**
- Fond bleu foncé avec texte gris clair peut être difficile à lire pour certains utilisateurs
- **Solution**: Augmenter légèrement le contraste (WCAG AA minimum: 4.5:1)

**Problème: Taille de police dans les sources**
- Le texte des prévisualisations de chunks est petit (apparemment ~12-13px)
- **Solution**: Augmenter à 14px minimum pour améliorer la lisibilité

**Problème: Pas de feedback audio/visuel sur les actions**
- Clic sur "Copier", "Régénérer", etc. ne donne pas de confirmation claire
- **Solution**: Ajouter des toasts/notifications temporaires

### 4. Ergonomie Générale

**Problème: Zone de saisie fixe en bas**
- Le champ de texte pourrait bénéficier d'un auto-expand pour les longs messages
- Actuellement limité à une seule ligne visible
- **Solution**: Textarea avec expansion automatique (max 5-6 lignes)

**Problème: Gestion du scroll**
- Pas de bouton "Scroll to bottom" visible si on remonte dans l'historique
- **Solution**: Ajouter un bouton flottant "↓ Nouveau message" quand on scroll up

**Problème: Pas de raccourcis clavier visibles**
- Impossible de savoir si Enter envoie le message ou si Shift+Enter fait un retour à la ligne
- **Solution**: Ajouter un hint discret sous le champ de saisie

### 5. Expérience Mobile

**Problème: Responsive perfectible**
- Sur écrans étroits, la sidebar devient modale mais cache le contenu principal
- Le hamburger menu nécessite plusieurs clics pour naviguer
- **Solution**: Revoir l'architecture mobile (bottom nav + hamburger menu)

---

## 🎨 Suggestions de Micro-interactions

1. **Hover states plus marqués**: Les éléments cliquables pourraient avoir des transitions plus fluides
2. **Animation d'apparition des messages**: Fade-in ou slide-in lors de l'ajout de nouveaux messages
3. **Pulse sur les nouvelles conversations**: Indicateur visuel pour attirer l'attention sur la sidebar
4. **Copy confirmation**: Toast "Copié !" après avoir cliqué sur le bouton copier
5. **Expand/collapse sources**: Permettre de replier les sections de sources pour gagner de l'espace

---

## 📊 Comparaison avec les Standards

| Critère | RAGBot | Standards Industry |
|---------|--------|-------------------|
| Design moderne | ✅ Excellent | ✅ Au niveau |
| Dark mode | ✅ Implémenté | ✅ Attendu |
| Sources traçables | ✅ Excellent | ⭐ Au-dessus |
| Feedback utilisateur | ⚠️ Basique | ❌ En dessous |
| Accessibilité | ⚠️ Moyen | ❌ En dessous |
| Mobile responsive | ⚠️ À améliorer | ❌ En dessous |
| États de chargement | ❌ Manquant | ❌ En dessous |

---

## 🔧 Recommandations Prioritaires

### Priorité 1 (Impact élevé, Effort faible)
1. ✅ Ajouter un loader/typing indicator pendant la génération de réponse
2. ✅ Ajouter des tooltips sur les boutons et toggles (Reranking, Export, etc.)
3. ✅ Améliorer le contraste des textes dans les cartes de sources
4. ✅ Ajouter des toasts de confirmation pour les actions (Copier, Régénérer)

### Priorité 2 (Impact élevé, Effort moyen)
5. 📱 Revoir l'architecture responsive mobile (sidebar + navigation)
6. 🔤 Rendre le champ de saisie auto-expandable (textarea)
7. ⌨️ Ajouter des hints de raccourcis clavier
8. 🔄 Ajouter un bouton "Scroll to bottom" flottant

### Priorité 3 (Impact moyen, Effort moyen)
9. 🎭 Améliorer les micro-interactions et transitions
10. 📂 Permettre le collapse/expand des sections de sources
11. 🎯 Améliorer la visibilité du menu utilisateur
12. ♿ Audit complet d'accessibilité WCAG 2.1 AA

---

## 💡 Inspirations et Références

**Bonnes pratiques observables sur**:
- **ChatGPT** (OpenAI): Typing indicators, scroll automatique, messages streaming
- **Claude** (Anthropic): Citations inline, feedback granulaire, markdown riche
- **Perplexity**: Affichage des sources avec preview, cards cliquables
- **Notion AI**: Tooltips contextuels, micro-interactions fluides

---

## 🎯 Conclusion

RAGBot offre une **expérience utilisateur solide** pour un outil professionnel RAG. Le système de sources traçables est particulièrement bien implémenté et constitue un avantage compétitif majeur.

Les principaux axes d'amélioration concernent:
1. **Le feedback système** (loaders, confirmations)
2. **L'accessibilité** (contrastes, tailles de police)
3. **L'expérience mobile** (responsive, navigation)

Avec ces ajustements, RAGBot pourrait facilement atteindre un score de **9/10** et se positionner parmi les meilleures interfaces RAG du marché.

---

**Rapport généré avec Claude Code + Playwright MCP**
**Méthodologie**: Navigation réelle, captures d'écran, analyse heuristique UX

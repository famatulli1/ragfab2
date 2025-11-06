# 📖 Guide Utilisateur - RAGFab

## Bienvenue sur votre assistant documentaire intelligent

RAGFab est votre assistant qui connaît toute la documentation de l'entreprise. Imaginez un collègue qui aurait lu et mémorisé tous les documents de l'entreprise et qui peut vous répondre instantanément. C'est exactement ce que fait RAGFab !

---

## 🚀 Premiers pas

### Comment poser une question ?

C'est aussi simple qu'envoyer un message :

1. **Tapez votre question** dans la zone de saisie en bas de l'écran
2. **Appuyez sur Entrée** ou cliquez sur le bouton d'envoi
3. **Attendez quelques secondes** : l'assistant cherche dans tous les documents
4. **Lisez la réponse** avec les sources citées en bas

**Exemple :**
```
❓ "Quelle est la procédure pour demander des congés ?"
```

L'assistant va chercher dans tous les documents RH, trouver la procédure exacte et vous la présenter de façon claire, avec les références des documents sources.

---

## 💬 Une conversation = Un sujet

### Pourquoi créer une nouvelle conversation pour chaque sujet ?

Pensez à vos conversations comme à des dossiers. Chaque dossier traite d'un sujet précis.

#### ✅ BONNE PRATIQUE

**Conversation 1 : Congés**
- "Quelle est la procédure pour poser des congés ?"
- "Combien de jours de congés ai-je par an ?"
- "Comment reporter des congés sur l'année suivante ?"

**Conversation 2 : Télétravail**
- "Quelle est notre politique de télétravail ?"
- "Comment demander une journée de télétravail ?"
- "Puis-je télétravailler depuis l'étranger ?"

#### ❌ MAUVAISE PRATIQUE

**Conversation mélangée :**
- "Quelle est la procédure pour poser des congés ?"
- "Comment fonctionne le télétravail ?"
- "Où trouver les horaires de la cantine ?"
- "Quelle est la politique de remboursement des frais ?"

> 💡 **Pourquoi ?** Quand vous mélangez les sujets, l'assistant peut se perdre et mélanger les informations. Une conversation par sujet = des réponses plus précises !

---

## 🎯 Comment bien poser vos questions

### Les questions efficaces

#### ✅ Questions claires et précises

**Bon exemple :**
```
"Quelle est la procédure pour déclarer un accident du travail ?"
```

**Pourquoi c'est bien ?**
- Le sujet est clair (accident du travail)
- L'objectif est précis (connaître la procédure)
- L'assistant sait exactement quoi chercher

#### ✅ Questions avec du contexte

**Bon exemple :**
```
"Je dois me rendre à un salon professionnel à Lyon.
Comment faire ma demande de remboursement de frais de déplacement ?"
```

**Pourquoi c'est bien ?**
- Le contexte est donné (salon professionnel)
- La situation est claire (déplacement à Lyon)
- La demande est précise (procédure de remboursement)

#### ❌ Questions trop vagues

**Mauvais exemple :**
```
"Les congés ?"
```

**Pourquoi c'est problématique ?**
- Trop vague : vous voulez connaître quoi exactement ?
- Le nombre de jours ? La procédure ? Les dates de pose ? Les reports ?

**Mieux formuler :**
```
"Combien de jours de congés payés ai-je droit chaque année ?"
```

---

## 🔄 Poser des questions de suite (suivi de conversation)

### L'assistant se souvient de votre conversation

Vous n'avez pas besoin de tout répéter à chaque question !

#### Exemple de conversation naturelle

**Question 1 :**
```
"Quelle est notre politique de télétravail ?"
```

**Réponse :** _L'assistant explique la politique complète_

**Question 2 :**
```
"Comment la demander ?"
```

**L'assistant comprend** que "la" fait référence au télétravail et vous explique la procédure de demande.

**Question 3 :**
```
"Et si ma demande est refusée ?"
```

**L'assistant comprend** toujours le contexte et vous explique les recours possibles.

### 💡 Astuce pour les questions courtes

L'assistant comprend les questions de suivi comme :
- "Comment faire ?"
- "Et celle de 2024 ?"
- "Pourquoi ?"
- "Combien ça coûte ?"
- "Et si ça ne marche pas ?"

> ⚠️ **Important** : Cela fonctionne uniquement dans la MÊME conversation. Si vous changez de conversation, l'assistant ne se souviendra pas du contexte précédent.

---

## 🔍 La recherche hybride : votre super-pouvoir

### C'est quoi la recherche hybride ?

Imaginez que vous cherchez dans une bibliothèque :

**📚 Recherche classique (sémantique)**
- Comprend le **sens** de votre question
- Trouve des documents qui parlent du même sujet, même avec des mots différents
- Exemple : "télétravail" trouvera aussi "travail à distance", "home office"

**🔎 Recherche hybride (sémantique + mots-clés)**
- Fait TOUT ce que la recherche classique fait
- **EN PLUS** : trouve les documents qui contiennent exactement les mots que vous cherchez
- Exemple : "RTT" trouvera précisément les documents contenant "RTT"

### Quand activer la recherche hybride ?

#### ✅ Activez-la pour :

**1. Les acronymes et sigles**
```
"Procédure RTT"
"Formulaire CERFA"
"Logiciel PeopleDoc"
```

**2. Les noms propres**
```
"Manuel du logiciel SAP"
"Procédure avec Chorus Pro"
"Formation Microsoft Teams"
```

**3. Les termes techniques précis**
```
"Installation pare-feu"
"Configuration VPN"
"Code comptable 606"
```

**4. Les références exactes**
```
"Article 3.2 du règlement intérieur"
"Formulaire demande congé"
"Annexe 5 de la convention collective"
```

#### ❌ Pas besoin pour :

**Les questions générales et conceptuelles**
```
"Comment améliorer ma productivité ?"
"Pourquoi favoriser le télétravail ?"
"Quels sont les avantages du travail en équipe ?"
```

> 💡 **Astuce** : Si votre question contient un acronyme, un nom de logiciel ou un terme technique précis, activez la recherche hybride !

### Comment activer la recherche hybride ?

1. **Repérez le bouton** en haut à droite de la zone de conversation
2. **Activez le toggle** "Recherche hybride"
3. **Ajustez le curseur** (facultatif) :
   - **← Vers la gauche (0.0 - 0.3)** : Priorité aux mots-clés exacts
   - **Au milieu (0.5)** : Équilibre parfait (recommandé)
   - **→ Vers la droite (0.7 - 1.0)** : Priorité au sens de la question

> 💡 **Conseil** : En cas de doute, laissez le curseur au milieu (0.5). Le système s'adapte automatiquement !

---

## 📚 Vérifier vos sources

### Pourquoi les sources sont importantes ?

Chaque réponse est accompagnée de **sources** : ce sont les documents exacts d'où viennent les informations.

#### À quoi servent les sources ?

✅ **Vérifier l'information** : Vous pouvez consulter le document original
✅ **Trouver plus de détails** : Le document complet contient souvent plus d'informations
✅ **Partager avec vos collègues** : Vous pouvez citer la référence exacte
✅ **Faire confiance** : Vous savez que la réponse vient d'un document officiel

### Comment lire les sources ?

Sous chaque réponse, vous trouvez :

```
📄 Sources consultées :
1. Règlement intérieur - Section 3.2 - Congés payés
2. Guide RH 2024 - Chapitre 5 - Procédures administratives
```

**Cliquez sur une source** pour voir exactement le passage du document utilisé.

> 💡 **Astuce** : Si une information vous semble étonnante, vérifiez toujours la source !

---

## ⭐ Bonnes pratiques : résumé

### ✅ À FAIRE

| Action | Exemple |
|--------|---------|
| **Créer une conversation par sujet** | Une conversation = télétravail, une autre = congés |
| **Poser des questions claires** | "Comment demander une formation professionnelle ?" |
| **Utiliser la recherche hybride pour les acronymes** | Activez pour "RTT", "CERFA", "PeopleDoc" |
| **Poser des questions de suivi** | "Comment faire ?", "Et si ça échoue ?" |
| **Vérifier les sources** | Cliquez sur les sources pour voir les documents originaux |
| **Donner du contexte** | "Je dois me déplacer à Lyon pour un salon, comment..." |

### ❌ À ÉVITER

| Action | Pourquoi c'est problématique |
|--------|------------------------------|
| **Mélanger plusieurs sujets** | L'assistant perd le fil et les réponses sont moins précises |
| **Questions d'un seul mot** | "Congés ?" → Trop vague, l'assistant ne sait pas quoi chercher |
| **Oublier le contexte** | "Elle coûte combien ?" → L'assistant ne sait pas de quoi vous parlez |
| **Ne pas vérifier les sources** | Vous pourriez passer à côté de détails importants |
| **Poser une question de suivi dans une nouvelle conversation** | L'assistant ne se souvient pas du contexte précédent |

---

## 🆘 Besoin d'aide ?

### La réponse n'est pas satisfaisante ?

**1. Reformulez votre question**
```
❌ "Les formations ?"
✅ "Comment m'inscrire à une formation professionnelle ?"
```

**2. Ajoutez du contexte**
```
❌ "Remboursement ?"
✅ "Je dois me rendre à un séminaire à Paris. Comment faire ma demande de remboursement de train ?"
```

**3. Essayez la recherche hybride**
- Si vous cherchez un terme précis (acronyme, nom de logiciel)
- Activez le toggle en haut de la page

**4. Créez une nouvelle conversation**
- Si vous changez complètement de sujet
- Cliquez sur "Nouvelle conversation"

### L'assistant ne trouve pas l'information ?

Plusieurs raisons possibles :
- **Le document n'existe pas** dans la base documentaire
- **La question est trop vague** : reformulez avec plus de précision
- **Le terme n'est pas dans les documents** : essayez avec des synonymes

> 💡 **Astuce** : Si vous cherchez "télétravail" et ne trouvez rien, essayez "travail à distance" ou "home office"

---

## 🎓 Exemples concrets d'utilisation

### Exemple 1 : Recherche de procédure

**Situation :** Vous voulez savoir comment déclarer un arrêt maladie

**✅ Bonne approche :**

1. Créez une nouvelle conversation : "Arrêt maladie"
2. Posez votre question principale :
   ```
   "Quelle est la procédure pour déclarer un arrêt maladie ?"
   ```
3. Questions de suivi dans la même conversation :
   ```
   "Dans quel délai dois-je envoyer le certificat ?"
   "À qui dois-je l'envoyer ?"
   "Et si je prolonge mon arrêt ?"
   ```

### Exemple 2 : Recherche de logiciel spécifique

**Situation :** Vous cherchez le manuel d'utilisation de PeopleDoc

**✅ Bonne approche :**

1. **Activez la recherche hybride** (curseur à 0.3 pour privilégier le nom exact)
2. Posez votre question :
   ```
   "Comment utiliser PeopleDoc pour demander un document RH ?"
   ```
3. L'assistant trouve les documents contenant exactement "PeopleDoc"

### Exemple 3 : Question conceptuelle

**Situation :** Vous voulez comprendre les avantages du télétravail

**✅ Bonne approche :**

1. **Laissez la recherche hybride désactivée** (recherche sémantique suffit)
2. Posez votre question :
   ```
   "Quels sont les avantages du télétravail pour les employés et l'entreprise ?"
   ```
3. L'assistant trouve tous les documents parlant des bénéfices, avantages, impacts positifs du télétravail

---

## 📊 Astuce bonus : évaluer les réponses

Sous chaque réponse, vous pouvez donner votre avis :
- 👍 **Réponse utile** : Cela aide à améliorer le système
- 👎 **Réponse peu utile** : Signalez les réponses insatisfaisantes

> Vos retours sont précieux pour améliorer continuellement l'assistant !

---

## 🎯 En résumé

RAGFab est votre bibliothécaire personnel qui :
- ✅ Connaît tous les documents de l'entreprise
- ✅ Comprend vos questions en langage naturel
- ✅ Trouve les informations précises avec les sources
- ✅ Se souvient du contexte de votre conversation
- ✅ S'adapte à vos besoins (recherche hybride)

**Trois règles d'or :**
1. **Un sujet = Une conversation**
2. **Soyez précis dans vos questions**
3. **Vérifiez toujours les sources**

---

*Bon travail avec votre assistant documentaire ! 🚀*

# Claude Audit - Analyse de la Mémoire Claude

Tu es un expert en optimisation de fichiers mémoire pour Claude Code. Analyse l'écosystème mémoire et propose des améliorations.

## Paramètres

- **mode** : {{ mode | default: "interactif" }} → interactif | auto
- **verbose** : {{ verbose | default: "false" }} → true | false

---

## ÉTAPE 1 : DÉCOUVERTE COMPLÈTE (UNE SEULE COMMANDE)

Exécute cette commande unique pour tout scanner :

```bash
echo "========== CLAUDE AUDIT - SCAN COMPLET =========="
echo ""
echo "=== STACK ==="
test -f package.json && echo "Node.js: $(node -v 2>/dev/null || echo 'installé')"
test -f pnpm-lock.yaml && echo "Package Manager: pnpm"
test -f yarn.lock && echo "Package Manager: yarn"
test -f package-lock.json && echo "Package Manager: npm"
test -f pyproject.toml && echo "Python détecté"
echo ""
echo "=== FICHIERS USER (~/.claude/) ==="
ls ~/.claude/*.md 2>/dev/null | while read f; do w=$(wc -w < "$f"); echo "$f: $w mots (~$((w * 13 / 10)) tokens)"; done
echo "TOTAL USER:" $(cat ~/.claude/*.md 2>/dev/null | wc -w | xargs) "mots"
echo ""
echo "=== FICHIERS PROJECT RACINE (*.md) ==="
ls *.md 2>/dev/null | while read f; do w=$(wc -w < "$f"); echo "$f: $w mots (~$((w * 13 / 10)) tokens)"; done
echo "TOTAL RACINE:" $(cat *.md 2>/dev/null | wc -w | xargs) "mots"
echo ""
echo "=== DOSSIER .claude/ ==="
ls -la .claude/ 2>/dev/null || echo "Pas de .claude/"
ls .claude/commands/*.md 2>/dev/null || echo "Pas de commandes projet"
echo ""
echo "=== COMMANDES USER ==="
ls ~/.claude/commands/*.md 2>/dev/null || echo "Pas de commandes user"
echo ""
echo "=== OUTILS CLI ==="
for tool in git gh node npm pnpm docker vercel; do command -v $tool >/dev/null 2>&1 && echo "✅ $tool" || echo "❌ $tool"; done
echo ""
echo "=== SCRIPTS PACKAGE.JSON ==="
test -f package.json && grep -A 20 '"scripts"' package.json | head -25
echo ""
echo "========== FIN SCAN =========="
```

---

## ÉTAPE 2 : LECTURE DES FICHIERS PRINCIPAUX

Lis ces fichiers s'ils existent :
1. `CLAUDE.md` (racine projet)
2. `~/.claude/CLAUDE.md` (config user)

Analyse leur contenu pour évaluer qualité et détecter redondances.

---

## ÉTAPE 3 : ANALYSE ET RAPPORT

Génère le rapport basé sur les données collectées.

### Format du rapport RÉSUMÉ :

```
╔═══════════════════════════════════════════════════════════════╗
║              🔍 CLAUDE AUDIT - Rapport                        ║
╠═══════════════════════════════════════════════════════════════╣
║  📅 Date : [date]                                             ║
║  📁 Projet : [chemin]                                         ║
║  🏷️  Stack : [détecté]                                        ║
╚═══════════════════════════════════════════════════════════════╝

💾 BUDGET TOKENS
───────────────────────────────────────────────────────────────
Mémoire totale : [X] tokens ([X]% de 200k)
├─ User (~/.claude/) : [X] tokens
└─ Project : [X] tokens

📊 SCORE GLOBAL : [X]/10
───────────────────────────────────────────────────────────────
[Évaluation sur 9 dimensions]

🎯 TOP 5 ACTIONS PRIORITAIRES
───────────────────────────────────────────────────────────────
1. [🔴/🟡/🟢] Description → Impact
2. ...

✅ VÉRIFICATIONS
───────────────────────────────────────────────────────────────
Outils CLI : [X]/[Y] installés
Scripts npm : Vérifiés
```

### Pour --verbose, ajoute :
- Détail de chaque fichier avec tokens
- Tableau complet des 9 dimensions
- Toutes les recommandations avec code

---

## ÉTAPE 4 : MODE INTERACTIF

Propose les améliorations avec menu numéroté :

```
Souhaitez-vous appliquer des améliorations ?
[1] Action 1
[2] Action 2
[3] Action 3
[T] Tout appliquer
[N] Non, juste le rapport
```

Attends la réponse avant d'agir.

---

## ÉTAPE 5 : APPLICATION

### Backup obligatoire avant modification :
```bash
mkdir -p .claude-backups
TIMESTAMP=$(date +%Y-%m-%d_%Hh%M)
cp [fichier] .claude-backups/[nom].$TIMESTAMP
```

### Puis applique les modifications demandées.

---

## RÈGLES

1. **UNE SEULE commande bash** pour le scan initial (évite multiples validations)
2. **Calculs réels** basés sur les données collectées
3. **Backup** avant toute modification
4. **Rapport en français**
5. **Recommandations concrètes** avec commandes exactes

---

## LANCER

Exécute le scan complet (étape 1), lis les fichiers principaux, puis génère le rapport.
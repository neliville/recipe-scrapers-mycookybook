# Workflow Git — MyCookyBook

> Guide de travail pour le fork [neliville/recipe-scrapers-mycookybook](https://github.com/neliville/recipe-scrapers-mycookybook)  
> Upstream : [hhursev/recipe-scrapers](https://github.com/hhursev/recipe-scrapers)

---

## 1. Modèle de branches

```
upstream/main  (hhursev/recipe-scrapers)
      │
      │  Sync Fork GitHub
      ▼
origin/main    ← reflète upstream + commits MyCookyBook mergés
      │
      │  branche develop
      ▼
origin/develop ← développement actif MyCookyBook
      │
      ├── feature/mycookybook-*   ← nouvelles fonctionnalités API
      └── fix/mycookybook-*       ← corrections API / déploiement
```

| Branche | Rôle | Déploiement |
|---|---|---|
| `main` | Stable, synchronisée upstream + MyCookyBook validé | Production o2switch |
| `develop` | Intégration continue MyCookyBook | Staging o2switch |
| `feature/*` | Développement isolé | Local uniquement |

---

## 2. Création de la branche `develop`

> À exécuter manuellement après le premier commit MyCookyBook.

```bash
# 1. S'assurer que main est propre et à jour
git checkout main
git status          # doit être clean (ou uniquement travail en cours)

# 2. Créer develop depuis main
git checkout -b develop

# 3. Pousser develop sur origin (quand prêt)
git push -u origin develop
```

**Convention** : tout nouveau développement MyCookyBook part de `develop`, jamais directement de modifications dans `recipe_scrapers/`.

---

## 3. Remotes

| Remote | URL | Usage |
|---|---|---|
| `origin` | `https://github.com/neliville/recipe-scrapers-mycookybook.git` | Fork MyCookyBook |
| `upstream` | `https://github.com/hhursev/recipe-scrapers.git` | Source officielle |

Vérifier la configuration :

```bash
git remote -v
```

Si `upstream` est absent :

```bash
git remote add upstream https://github.com/hhursev/recipe-scrapers.git
```

---

## 4. Workflow Sync Fork (upstream → main)

### Option A — Sync Fork GitHub (recommandée)

1. Aller sur GitHub → fork → **Sync fork** → **Update branch**
2. GitHub merge automatiquement les commits upstream dans `origin/main`
3. Mettre à jour le clone local :

```bash
git checkout main
git pull origin main
```

### Option B — Merge manuel (si conflit ou contrôle fin)

```bash
git checkout main
git fetch upstream
git merge upstream/main
# Résoudre les conflits si nécessaire (uniquement dans les zones MyCookyBook)
git push origin main
```

### Règles pendant le Sync Fork

| Zone | Action |
|---|---|
| `recipe_scrapers/` | Accepter upstream tel quel |
| `tests/` | Accepter upstream tel quel |
| `mycookybook_api/` | **Ne jamais écraser** — hors périmètre upstream |
| `deploy/` | **Ne jamais écraser** |
| `docs/MYCOOKYBOOK_*`, `docs/GIT_*` | **Ne jamais écraser** |
| `.gitattributes` | Conserver la version MyCookyBook |

---

## 5. Stratégie de merge upstream → develop

Après chaque Sync Fork sur `main` :

```bash
git checkout develop
git merge main
# Résoudre conflits éventuels
git push origin develop
```

**Fréquence recommandée** : synchroniser upstream **avant** chaque cycle de développement significatif (toutes les 2–4 semaines ou avant une release).

---

## 6. Workflow développement MyCookyBook

```bash
# 1. Partir de develop à jour
git checkout develop
git pull origin develop

# 2. Créer une branche feature
git checkout -b feature/mycookybook-parse-ingredients-v2

# 3. Développer (uniquement dans mycookybook_api/, deploy/, docs/MyCookyBook)
#    NE PAS modifier recipe_scrapers/

# 4. Commiter
git add mycookybook_api/ deploy/ docs/MYCOOKYBOOK_*
git commit -m "feat(api): description du changement"

# 5. Merger dans develop
git checkout develop
git merge feature/mycookybook-parse-ingredients-v2
git push origin develop

# 6. Déployer sur staging o2switch (git pull sur le serveur)
```

---

## 7. Stratégie staging → production

```
develop  ──(tests staging OK)──►  main  ──(déploiement prod)──►  api.mycookybook.com
   │                                  │
   └── staging-api.mycookybook.com    └── tag release optionnel
```

### Cycle de release

| Étape | Branche | Environnement | Action |
|---|---|---|---|
| 1. Développement | `feature/*` → `develop` | Local | Tests unitaires API |
| 2. Intégration | `develop` | Staging o2switch | `git pull origin develop` + tests curl |
| 3. Validation | `develop` | Staging | Checklist endpoints (voir `deploy/o2switch-staging.md`) |
| 4. Release | `develop` → `main` | — | Merge + tag `v2.x.x` |
| 5. Production | `main` | Production o2switch | `git pull origin main` + restart Passenger |

### Merge develop → main (release)

```bash
git checkout main
git pull origin main
git merge develop
git tag -a v2.1.0 -m "Release MyCookyBook API 2.1.0"
git push origin main --tags
```

### Rollback production

```bash
# Sur le serveur o2switch
cd /home/iwob6566/public_html/api.mycookybook.com
git checkout v2.0.0    # tag stable précédent
source ~/venv/production-api/bin/activate
pip install -e .
pip install -r mycookybook_api/requirements.txt
# Redémarrer l'app Python dans cPanel
```

---

## 8. Premier commit (état actuel)

Le dépôt local est propre (CRLF corrigé). Fichiers untracked MyCookyBook en attente :

```bash
# Commit 1 — structure et code API
git add mycookybook_api/ deploy/
git commit -m "Add MyCookyBook API structure and deployment docs"

# Commit 2 — documentation et scripts Git
git add docs/MYCOOKYBOOK_MIGRATION_PLAN.md docs/GIT_CLEANUP_PLAN.md \
        docs/PROJECT_STRUCTURE_AUDIT.md docs/GIT_WORKFLOW.md \
        docs/GITATTRIBUTES_RECOMMENDED.md docs/MYCOOKYBOOK_ROADMAP.md \
        deploy/o2switch-staging.md deploy/o2switch-production.md \
        scripts/git-cleanup.sh scripts/git-config-recommended.sh
git commit -m "Add MyCookyBook project documentation and Git utilities"

# Commit 3 — .gitattributes (manuel, séparé)
# git add .gitattributes
# git commit -m "Add .gitattributes for LF normalization"

# Créer develop
git checkout -b develop
git push -u origin develop
git checkout main
git push origin main
```

> Adapter les messages et le découpage des commits selon votre préférence. L'important est de **ne jamais** inclure de modifications `recipe_scrapers/` involontaires.

---

## 9. Configuration Git WSL (déjà appliquée)

```bash
git config --global core.autocrlf input
git config --global core.eol lf
```

Voir aussi [`scripts/git-config-recommended.sh`](../scripts/git-config-recommended.sh).

---

## 10. Checklist avant Sync Fork

- [ ] `git status` clean sur `main`
- [ ] `.gitattributes` commité
- [ ] `core.autocrlf input` configuré
- [ ] Tests locaux passent (`pytest tests/` upstream + futurs tests API)
- [ ] Staging validé si release imminente

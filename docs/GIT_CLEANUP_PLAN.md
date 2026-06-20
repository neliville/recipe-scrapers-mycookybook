# Git LF/CRLF — Plan de nettoyage MyCookyBook

> Rapport généré le 20 juin 2026  
> Phase actuelle : **analyse et préparation** — aucune action Git automatique

---

## 1. Résumé exécutif

Le dépôt `neliville/recipe-scrapers-mycookybook` affiche environ **2519 fichiers modifiés** dans `git status`. Après vérification, ces modifications ne reflètent **aucun changement de contenu** : elles sont exclusivement dues à une conversion de fins de ligne **LF → CRLF** dans l'arbre de travail (environnement WSL/Windows).

**Objectif** : restaurer un état Git propre sans committer les faux positifs CRLF, tout en **préservant les 17 fichiers spécifiques MyCookyBook** (6 déjà trackés + 11 nouveaux non suivis).

**Actions proposées** (exécution manuelle uniquement) :

1. Configurer Git (`core.autocrlf input`) — voir [`scripts/git-config-recommended.sh`](../scripts/git-config-recommended.sh)
2. Sauvegarder puis nettoyer — voir [`scripts/git-cleanup.sh`](../scripts/git-cleanup.sh)
3. Commiter uniquement les fichiers MyCookyBook (session ultérieure)
4. Optionnel : ajouter un `.gitattributes` (proposition ci-dessous, **non créé automatiquement**)

---

## 2. État Git actuel

| Élément | Détail |
|---|---|
| Branche | `main` |
| Synchronisation | À jour avec `origin/main` (snapshot du 20 juin 2026) |
| Remote `origin` | `https://github.com/neliville/recipe-scrapers-mycookybook.git` |
| Remote `upstream` | `https://github.com/hhursev/recipe-scrapers.git` |
| `.gitattributes` | **Absent** |
| `core.autocrlf` (repo) | Non configuré |
| `core.filemode` | `false` (typique WSL/Windows) |

### Commits MyCookyBook spécifiques (au-dessus de l'upstream)

```
11c95f32 Rename units_multilingual_complete (1).json to units_multilingual_complete.json
0723ab63 Add files via upload
51cea4af Add README file for MyCookyBook API
```

### Diagnostic CRLF (vérifications réalisées)

```bash
git ls-files --eol recipe_scrapers/__init__.py
# Résultat : i/lf w/crlf attr/
#   i/lf     → index Git stocke LF
#   w/crlf   → working tree contient CRLF
#   attr/    → aucun attribut EOL (.gitattributes absent)

git diff --ignore-space-at-eol -- recipe_scrapers/__init__.py
# Résultat : aucune différence
```

**Conclusion** : le fork upstream n'est pas réellement modifié. Les ~2519 entrées `modified` sont des artefacts CRLF.

---

## 3. Compteurs

| Catégorie | Nombre | Détail |
|---|---:|---|
| Fichiers `modified` (total) | **2519** | Dont 2514 upstream + 5 MyCookyBook trackés (CRLF uniquement) |
| Fichiers upstream réellement modifiés | **0** | Validé via `--ignore-space-at-eol` |
| Fichiers MyCookyBook nouveaux (untracked) | **11** | Phase 1 structure + documentation déploiement |
| Fichiers MyCookyBook trackés (CRLF phantom) | **5** | Contenu identique à HEAD, EOL différent |
| Fichiers MyCookyBook trackés (propres) | **1** | `mycookybook_api/app.py` — non listé en modified |
| **Total fichiers MyCookyBook** | **17** | Inventaire complet ci-dessous |

---

## 4. Liste complète des fichiers MyCookyBook

### 4.1 Déjà commités sur `origin/main` (6 fichiers)

| Fichier | Statut Git | Nature de la modification |
|---|---|---|
| `mycookybook_api/app.py` | Propre | Aucune (non listé en modified) |
| `mycookybook_api/passenger_wsgi.py` | `modified` | CRLF uniquement |
| `mycookybook_api/requirements.txt` | `modified` | CRLF uniquement |
| `mycookybook_api/README.md` | `modified` | CRLF uniquement |
| `mycookybook_api/ingredients_multilingual_complete.json` | `modified` | CRLF uniquement |
| `mycookybook_api/units_multilingual_complete.json` | `modified` | CRLF uniquement |

### 4.2 Nouveaux fichiers MyCookyBook — untracked (11 fichiers)

**Documentation déploiement — `deploy/`**

| Fichier |
|---|
| `deploy/README.md` |
| `deploy/staging.md` |
| `deploy/production.md` |

**Documentation migration — `docs/`**

| Fichier |
|---|
| `docs/MYCOOKYBOOK_MIGRATION_PLAN.md` |

**Structure phase 1 — `mycookybook_api/`**

| Fichier |
|---|
| `mycookybook_api/__init__.py` |
| `mycookybook_api/templates/.gitkeep` |
| `mycookybook_api/static/.gitkeep` |
| `mycookybook_api/services/__init__.py` |
| `mycookybook_api/parsers/__init__.py` |
| `mycookybook_api/config/__init__.py` |
| `mycookybook_api/tests/__init__.py` |

### 4.3 Arborescence MyCookyBook complète

```
recipe-scrapers-mycookybook/
├── deploy/
│   ├── README.md
│   ├── staging.md
│   └── production.md
├── docs/
│   └── MYCOOKYBOOK_MIGRATION_PLAN.md
└── mycookybook_api/
    ├── __init__.py
    ├── app.py                          ← tracké, propre
    ├── passenger_wsgi.py               ← tracké, CRLF phantom
    ├── requirements.txt                ← tracké, CRLF phantom
    ├── README.md                       ← tracké, CRLF phantom
    ├── ingredients_multilingual_complete.json  ← tracké, CRLF phantom
    ├── units_multilingual_complete.json        ← tracké, CRLF phantom
    ├── templates/.gitkeep              ← untracked
    ├── static/.gitkeep                 ← untracked
    ├── services/__init__.py            ← untracked
    ├── parsers/__init__.py             ← untracked
    ├── config/__init__.py              ← untracked
    └── tests/__init__.py               ← untracked
```

---

## 5. Fichiers upstream affectés (CRLF phantom uniquement)

Les **2514 fichiers upstream** apparaissent en `modified` sans changement sémantique. Répartition par catégorie :

| Catégorie | Exemples |
|---|---|
| `recipe_scrapers/` | ~626 scrapers + modules core |
| `tests/` | Tests unitaires + `tests/test_data/` (~2400 fichiers JSON/HTML) |
| `docs/` (upstream) | MkDocs, guides contributing |
| CI / config | `.github/`, `.pre-commit-config.yaml`, `pyproject.toml`, `mkdocs.yaml`, `.flake8`, `.gitignore` |
| Racine | `README.rst`, `LICENSE`, `generate.py` |

**Aucun de ces fichiers ne doit être commité** dans le cadre du nettoyage CRLF.

---

## 6. Autres fichiers volontairement modifiés ?

**Non.**

- Sur l'ensemble des fichiers upstream : `git diff --ignore-space-at-eol` ne révèle aucune différence.
- Les seules modifications réelles sont les **11 fichiers untracked MyCookyBook** créés en phase 1 (structure + documentation).
- `app.py` et `passenger_wsgi.py` n'ont **pas** été modifiés volontairement ; `passenger_wsgi.py` apparaît en `modified` uniquement à cause du CRLF préexistant.

---

## 7. Absence de `.gitattributes` — proposition recommandée

Le dépôt **ne contient pas** de fichier `.gitattributes`. Ce fichier n'a **pas été créé** automatiquement.

Contenu recommandé à ajouter manuellement **après** le nettoyage CRLF, dans un commit dédié :

```gitattributes
* text=auto
*.py text eol=lf
*.yml text eol=lf
*.yaml text eol=lf
*.md text eol=lf
*.json text eol=lf
*.sh text eol=lf
```

**Pourquoi** : force la normalisation LF à la prochaine réécriture des fichiers, complète `core.autocrlf input`, et protège le dépôt lors des Sync Fork upstream.

**Attention** : l'ajout de `.gitattributes` peut provoquer une réécriture EOL au prochain checkout. À faire **après** le nettoyage et **avant** le prochain Sync Fork.

---

## 8. Stratégie de nettoyage recommandée

### Phase 0 — Prérequis

1. Relire ce document intégralement.
2. Vérifier l'état actuel :
   ```bash
   git status --short | wc -l          # attendu : ~2530 (2519 modified + 11 untracked)
   git status --short | grep '^??'       # attendu : deploy/, docs/MYCOOKYBOOK..., mycookybook_api/...
   ```
3. S'assurer qu'aucun travail en cours non sauvegardé n'existe hors MyCookyBook.

### Phase 1 — Configuration Git

Exécuter manuellement :

```bash
bash scripts/git-config-recommended.sh
```

Configure `core.autocrlf input` (recommandé WSL/Linux) pour éviter la reconversion CRLF future.

### Phase 2 — Nettoyage CRLF

Exécuter manuellement (avec confirmation interactive) :

```bash
bash scripts/git-cleanup.sh
```

Le script :
1. Sauvegarde les 17 fichiers MyCookyBook dans `/tmp/mycookybook-backup-<timestamp>/`
2. Exécute `git restore --worktree .` (annule les 2519 faux positifs CRLF)
3. Vérifie que les untracked MyCookyBook sont intacts
4. Restaure depuis le backup si une perte est détectée

**Ce que le script ne fait PAS** : `git clean`, `git reset --hard`, commit, push.

### Phase 3 — Vérification post-nettoyage

```bash
# Aucun fichier modified attendu
git status --short | grep -v '^??' | wc -l    # attendu : 0

# Uniquement les untracked MyCookyBook
git status --short                             # attendu : ~11 lignes ??

# Pas de diff sémantique résiduel
git diff --ignore-space-at-eol                 # attendu : vide

# EOL normalisé (après config autocrlf input + restore)
git ls-files --eol recipe_scrapers/__init__.py   # attendu : i/lf w/lf
```

### Phase 4 — Commit MyCookyBook (session ultérieure)

```bash
git add deploy/ docs/MYCOOKYBOOK_MIGRATION_PLAN.md mycookybook_api/__init__.py \
        mycookybook_api/templates/ mycookybook_api/static/ \
        mycookybook_api/services/ mycookybook_api/parsers/ \
        mycookybook_api/config/ mycookybook_api/tests/

git status   # vérifier : uniquement les fichiers MyCookyBook staged

git commit -m "Add MyCookyBook structure and deployment documentation"
```

### Phase 5 — Optionnel : `.gitattributes`

Créer manuellement le fichier `.gitattributes` avec le contenu de la section 7, puis commit séparé.

---

## 9. Checklist de validation manuelle

- [ ] `git status` confirme ~2519 modified avant nettoyage
- [ ] `git-config-recommended.sh` exécuté — `core.autocrlf` = `input`
- [ ] `git-cleanup.sh` exécuté avec confirmation
- [ ] 0 fichier `modified` après nettoyage
- [ ] 11 fichiers untracked MyCookyBook présents
- [ ] Backup conservé dans `/tmp/mycookybook-backup-*`
- [ ] `git diff --ignore-space-at-eol` vide
- [ ] Commit MyCookyBook effectué séparément (si souhaité)
- [ ] `.gitattributes` ajouté manuellement (optionnel)

---

## 10. Risques et mitigations

| Risque | Sévérité | Mitigation |
|---|---|---|
| Perte des fichiers untracked MyCookyBook | Élevée si `git clean -fd` | Script sans `git clean` ; backup préalable des 17 fichiers |
| `git restore` sur fichiers MyCookyBook trackés | Faible | Remet LF depuis HEAD ; contenu identique si CRLF seul |
| Snapshot Git obsolète | Moyenne | Relancer `git status` avant exécution |
| `core.autocrlf true` sous Windows natif | Élevée | Utiliser `input` sous WSL, pas `true` |
| Sync Fork upstream futur | Moyenne | `.gitattributes` + `autocrlf input` avant sync |
| Confusion modified / untracked | Faible | Ce rapport distingue 6 trackés vs 11 untracked |
| Commit accidentel des 2519 CRLF | Élevée | Ne jamais `git add .` avant nettoyage |

---

## 11. Scripts associés

| Script | Rôle |
|---|---|
| [`scripts/git-config-recommended.sh`](../scripts/git-config-recommended.sh) | Configuration `core.autocrlf input` + vérifications |
| [`scripts/git-cleanup.sh`](../scripts/git-cleanup.sh) | Backup, nettoyage CRLF, vérifications, restauration conditionnelle |

**Important** : ces scripts sont fournis à titre d'aide. Ils ne s'exécutent pas automatiquement. L'utilisateur doit les lancer manuellement après validation de ce plan.

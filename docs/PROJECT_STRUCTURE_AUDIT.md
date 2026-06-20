# Audit de structure — MyCookyBook

> Rapport généré le 20 juin 2026  
> Phase : **préparation avant premier commit** — dépôt Git propre (CRLF corrigé)

---

## 1. Résumé

Le dépôt `recipe-scrapers-mycookybook` est structuré autour de deux périmètres distincts :

| Périmètre | Dossiers | Règle |
|---|---|---|
| **Upstream** | `recipe_scrapers/`, `tests/`, `docs/` (MkDocs), `.github/`, `pyproject.toml`, etc. | Ne pas modifier volontairement |
| **MyCookyBook** | `mycookybook_api/`, `deploy/`, `docs/MYCOOKYBOOK_*`, `docs/GIT_*`, `scripts/git-*` | Code et docs métier MyCookyBook |

**Verdict global** : la structure MyCookyBook est **cohérente et prête pour le premier commit**, avec quelques incohérences documentaires mineures à résoudre avant déploiement o2switch.

---

## 2. Arborescence actuelle

```
recipe-scrapers-mycookybook/
│
├── recipe_scrapers/              # upstream — 626+ scrapers (NE PAS MODIFIER)
├── tests/                        # upstream — tests unitaires + test_data
├── templates/scraper.py          # upstream — boilerplate dev scrapers
├── scripts/
│   ├── update_test.py            # upstream
│   ├── reorder_json_keys.py      # upstream
│   ├── git-cleanup.sh            # MyCookyBook — nettoyage CRLF (exécuté)
│   └── git-config-recommended.sh # MyCookyBook — config Git WSL
│
├── docs/
│   ├── contributing/             # upstream — MkDocs
│   ├── getting-started/          # upstream — MkDocs
│   ├── GIT_CLEANUP_PLAN.md       # MyCookyBook — rapport CRLF
│   └── MYCOOKYBOOK_MIGRATION_PLAN.md  # MyCookyBook — plan migration
│
├── deploy/                       # MyCookyBook — documentation déploiement
│   ├── README.md
│   ├── staging.md
│   └── production.md
│
├── mycookybook_api/              # MyCookyBook — API Flask
│   ├── __init__.py               # package, version 2.0
│   ├── app.py                    # monolithique (~1346 lignes) — NE PAS MODIFIER (phase actuelle)
│   ├── passenger_wsgi.py         # entry WSGI — NE PAS MODIFIER (phase actuelle)
│   ├── requirements.txt
│   ├── README.md
│   ├── ingredients_multilingual_complete.json  # ~9977 entrées, non utilisé par app.py
│   ├── units_multilingual_complete.json        # utilisé par app.py (ligne 950)
│   ├── templates/.gitkeep
│   ├── static/.gitkeep
│   ├── services/__init__.py      # vide — phase 2
│   ├── parsers/__init__.py       # vide — phase 2
│   ├── config/__init__.py        # vide — phase 2
│   └── tests/__init__.py         # vide — phase 2
│
├── pyproject.toml                # upstream
├── README.rst                    # upstream
├── mkdocs.yaml                   # upstream
└── .gitattributes                # ABSENT
```

### Fichiers untracked MyCookyBook (en attente de commit)

| Dossier / fichier | Fichiers |
|---|---|
| `deploy/` | 3 fichiers `.md` |
| `docs/GIT_CLEANUP_PLAN.md` | 1 |
| `docs/MYCOOKYBOOK_MIGRATION_PLAN.md` | 1 |
| `mycookybook_api/` | 14 fichiers (7 core + 7 structure phase 1) |
| `scripts/git-cleanup.sh` | 1 |
| `scripts/git-config-recommended.sh` | 1 |

**Total MyCookyBook untracked** : ~21 fichiers (hors docs générés par cette phase).

---

## 3. Arborescence recommandée (cible)

```
recipe-scrapers-mycookybook/
│
├── recipe_scrapers/              # upstream — sync fork uniquement
├── tests/                        # upstream
│
├── mycookybook_api/              # API Flask MyCookyBook
│   ├── app.py                    # routes JSON (phase 2 : refactor services/)
│   ├── passenger_wsgi.py         # ou wrapper root (voir deploy/o2switch-*.md)
│   ├── requirements.txt
│   ├── config/                   # settings staging/prod
│   ├── services/                 # logique scrape / parse
│   ├── parsers/                  # MultilingualIngredientParser
│   ├── tests/                    # tests API
│   ├── templates/                # futurs templates HTML (si besoin)
│   └── static/                   # futurs assets
│
├── deploy/
│   ├── README.md                 # index déploiement
│   ├── staging.md                # guide générique (legacy)
│   ├── production.md             # guide générique (legacy)
│   ├── o2switch-staging.md       # guide o2switch détaillé ← NOUVEAU
│   └── o2switch-production.md    # guide o2switch détaillé ← NOUVEAU
│
├── docs/
│   ├── MYCOOKYBOOK_MIGRATION_PLAN.md
│   ├── MYCOOKYBOOK_ROADMAP.md    ← NOUVEAU
│   ├── PROJECT_STRUCTURE_AUDIT.md  ← ce fichier
│   ├── GIT_CLEANUP_PLAN.md
│   ├── GIT_WORKFLOW.md           ← NOUVEAU
│   └── GITATTRIBUTES_RECOMMENDED.md  ← NOUVEAU (proposition, pas le fichier réel)
│
├── scripts/
│   ├── git-cleanup.sh
│   └── git-config-recommended.sh
│
├── passenger_wsgi.py             # OPTIONNEL phase 2 — wrapper root o2switch
└── .gitattributes                # À créer manuellement (voir GITATTRIBUTES_RECOMMENDED.md)
```

---

## 4. Audit par dossier

### 4.1 `mycookybook_api/` — Cohérent

| Élément | Statut | Détail |
|---|---|---|
| `__init__.py` | OK | Package déclaré, `__version__ = "2.0"` |
| `app.py` | OK (legacy) | 5 routes JSON, monolithique, fonctionnel |
| `passenger_wsgi.py` | OK (legacy) | Import relatif `from app import app` — adapté si CWD = `mycookybook_api/` |
| `requirements.txt` | OK | Flask + recipe-scrapers + dépendances scrape |
| JSON units | OK | Utilisé par `app.py` |
| JSON ingredients | Attention | Présent mais **non chargé** par `app.py` — prévu phase 2 |
| `templates/`, `static/` | OK | `.gitkeep` — pas de templates Flask utilisés actuellement |
| `services/`, `parsers/`, `config/`, `tests/` | OK | Squelettes vides — prêts pour refactor phase 2 |

**Routes Flask confirmées** :

| Route | Méthodes |
|---|---|
| `/` | GET |
| `/scrape` | GET, POST |
| `/scrape-v2` | GET, POST |
| `/parse-ingredient` | POST |
| `/parse-ingredients` | POST |

### 4.2 `deploy/` — Cohérent avec réserve

| Fichier | Statut | Remarque |
|---|---|---|
| `README.md` | OK | Vue d'ensemble o2switch |
| `staging.md` | Attention | App root = `.../mycookybook_api` — **approche legacy** |
| `production.md` | Attention | Idem — à aligner avec `o2switch-*.md` |

Les guides `o2switch-staging.md` et `o2switch-production.md` (nouveaux) documentent l'approche recommandée : **Application root = racine du clone**.

### 4.3 `docs/` — Cohérent

| Fichier MyCookyBook | Statut |
|---|---|
| `MYCOOKYBOOK_MIGRATION_PLAN.md` | OK — analyse complète phase 1 |
| `GIT_CLEANUP_PLAN.md` | OK — CRLF résolu |

Les sous-dossiers `contributing/` et `getting-started/` sont **upstream MkDocs** — ne pas mélanger avec la doc MyCookyBook.

### 4.4 `scripts/` — Cohérent

| Script | Rôle | Statut |
|---|---|---|
| `git-cleanup.sh` | Nettoyage CRLF | Exécuté avec succès |
| `git-config-recommended.sh` | Config WSL | Exécuté (`autocrlf=input`, `eol=lf`) |
| `update_test.py` | Upstream | Ne pas modifier |
| `reorder_json_keys.py` | Upstream | Ne pas modifier |

---

## 5. Incohérences identifiées

| # | Incohérence | Sévérité | Recommandation |
|---|---|---|---|
| 1 | **App root o2switch** : `staging.md` / `production.md` pointent sur `mycookybook_api/` ; nouvelle recommandation = racine du clone | Moyenne | Suivre `deploy/o2switch-*.md` ; mettre à jour `staging.md` / `production.md` ultérieurement |
| 2 | **Chemin JSON relatif** dans `app.py` : `open('units_multilingual_complete.json')` dépend du CWD Passenger | Élevée (déploiement) | Corriger en phase 2 avec `Path(__file__).resolve().parent` — hors scope actuel |
| 3 | **`ingredients_multilingual_complete.json` non utilisé** | Faible | Documenté ; intégration phase 2 |
| 4 | **`.gitattributes` absent** | Moyenne | Créer manuellement avant Sync Fork (voir `GITATTRIBUTES_RECOMMENDED.md`) |
| 5 | **`ingredient-parser-nlp` dans requirements.txt** mais non importé dans `app.py` | Faible | Retirer ou utiliser en phase 2 |
| 6 | **Pas de branche `develop`** | Faible | Créer lors du premier commit (voir `GIT_WORKFLOW.md`) |
| 7 | **Pas de tests API** | Moyenne | Ajouter dans `mycookybook_api/tests/` en phase 2 |
| 8 | **`passenger_wsgi.py` import relatif** | Moyenne | Fonctionne si Passenger CWD = `mycookybook_api/` ; wrapper root possible en phase 2 |

---

## 6. Recommandations

### Immédiat (avant premier commit)

1. Commiter tous les fichiers MyCookyBook untracked en **un ou deux commits dédiés** (structure + docs).
2. Créer manuellement `.gitattributes` (contenu dans `GITATTRIBUTES_RECOMMENDED.md`).
3. Créer la branche `develop` (procédure dans `GIT_WORKFLOW.md`).

### Court terme (phase 2 — code)

1. Corriger le chemin JSON dans `app.py` (`Path(__file__)`).
2. Refactoriser progressivement vers `services/` et `parsers/`.
3. Ajouter tests API dans `mycookybook_api/tests/`.
4. Évaluer un `passenger_wsgi.py` wrapper à la racine du clone pour o2switch.

### Moyen terme (déploiement)

1. Déployer staging selon `deploy/o2switch-staging.md`.
2. Valider tous les endpoints curl.
3. Promouvoir vers production selon `deploy/o2switch-production.md`.

### Long terme (architecture)

1. Intégration avec Symfony MyCookyBook (voir `MYCOOKYBOOK_ROADMAP.md`).
2. Sync Fork upstream régulier sur `main`, merge vers `develop`.

---

## 7. Checklist de cohérence

- [x] `mycookybook_api/` contient tous les fichiers core API
- [x] Structure phase 1 (`services/`, `parsers/`, etc.) en place
- [x] `deploy/` documente staging et production
- [x] Docs MyCookyBook séparées de la doc upstream MkDocs
- [x] Scripts Git utilitaires présents et testés (CRLF)
- [x] `recipe_scrapers/` non modifié
- [x] `app.py` et `passenger_wsgi.py` non modifiés
- [ ] `.gitattributes` à créer manuellement
- [ ] Branche `develop` à créer
- [ ] Guides o2switch alignés (nouveaux fichiers `o2switch-*.md`)

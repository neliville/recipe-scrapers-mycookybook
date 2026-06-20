# MyCookyBook — Plan de migration

> Rapport généré le 20 juin 2026  
> Phase actuelle : **préparation structurelle** (sans modification de code Python)

---

## 1. Contexte

| Élément | Détail |
|---|---|
| Fork | [neliville/recipe-scrapers-mycookybook](https://github.com/neliville/recipe-scrapers-mycookybook) |
| Upstream | [hhursev/recipe-scrapers](https://github.com/hhursev/recipe-scrapers) |
| Remote upstream | `upstream → hhursev/recipe-scrapers` (configuré) |
| Objectif | Isoler le code métier MyCookyBook tout en gardant le Sync Fork GitHub |

### Commits MyCookyBook spécifiques (au-dessus de l'upstream)

```
11c95f32 Rename units_multilingual_complete (1).json to units_multilingual_complete.json
0723ab63 Add files via upload
51cea4af Add README file for MyCookyBook API
```

---

## 2. Arborescence actuelle

```
recipe-scrapers-mycookybook/
├── .github/                    # upstream — CI, issue templates
├── docs/                       # upstream — MkDocs (+ ce rapport)
├── mycookybook_api/            # MyCookyBook — API Flask
│   ├── app.py                  # 1346 lignes, monolithique
│   ├── passenger_wsgi.py       # entry point WSGI actuel
│   ├── requirements.txt
│   ├── ingredients_multilingual_complete.json
│   ├── units_multilingual_complete.json
│   └── README.md
├── recipe_scrapers/            # upstream — 626 scrapers + core
│   ├── plugins/
│   └── settings/
├── scripts/                    # upstream
├── templates/                  # upstream — scraper.py (boilerplate dev)
├── tests/                      # upstream — tests recipe_scrapers
├── pyproject.toml              # upstream
├── README.rst                  # upstream
└── mkdocs.yaml                 # upstream
```

---

## 3. Arborescence recommandée (cible)

```
recipe-scrapers-mycookybook/
│
├── recipe_scrapers/            # upstream — NE PAS MODIFIER
├── docs/
│   └── MYCOOKYBOOK_MIGRATION_PLAN.md
├── tests/                      # upstream
├── deploy/                     # MyCookyBook — documentation déploiement
│   ├── README.md
│   ├── staging.md
│   └── production.md
│
└── mycookybook_api/            # MyCookyBook — isolé
    ├── __init__.py             # package Python
    ├── passenger_wsgi.py
    ├── app.py
    ├── requirements.txt
    ├── ingredients_multilingual_complete.json
    ├── units_multilingual_complete.json
    ├── templates/              # prêt pour futurs templates HTML
    ├── static/                 # prêt pour futurs assets statiques
    ├── services/               # logique métier (phase 2)
    ├── parsers/                # parseur ingrédients (phase 2)
    ├── config/                 # configuration (phase 2)
    └── tests/                  # tests API (phase 2)
```

---

## 4. Analyse de app.py

### Routes Flask (100 % JSON, aucun template HTML)

| Route | Méthodes | Description |
|---|---|---|
| `/` | GET | Documentation JSON |
| `/scrape` | GET, POST | Scrape recette + parsing ingrédients |
| `/scrape-v2` | GET, POST | Scrape alternatif avec score qualité |
| `/parse-ingredient` | POST | Parse un ingrédient |
| `/parse-ingredients` | POST | Parse une liste d'ingrédients |

### Recherche templates / static

| Pattern recherché | Résultat |
|---|---|
| `render_template(...)` | **Absent** |
| `template_folder` | **Absent** |
| `static_folder` | **Absent** |
| `send_from_directory` | **Absent** |
| `url_for(...)` | **Absent** |

Flask instancié simplement : `app = Flask(__name__)` (ligne 943).

**Conclusion** : aucun template Flask MyCookyBook à déplacer.  
Le fichier `templates/scraper.py` à la racine est un boilerplate **upstream** pour créer de nouveaux scrapers — ne pas toucher.

### Fichiers JSON

| Fichier | Utilisé dans app.py | Remarque |
|---|---|---|
| `units_multilingual_complete.json` | Oui (ligne 950) | Chargé avec chemin relatif CWD — fragile sous Passenger |
| `ingredients_multilingual_complete.json` | **Non** | Présent (~9977 entrées), prévu pour usage futur |

---

## 5. Dépendances

### mycookybook_api/requirements.txt

```
Flask>=2.0
werkzeug==3.0.1
recipe-scrapers>=15.0
requests>=2.28
beautifulsoup4>=4.9
lxml==5.0
ingredient-parser-nlp~=2.4.0
extruct>=0.16
w3lib>=2.2
```

### pyproject.toml (upstream)

```
beautifulsoup4 >= 4.12.3
extruct >= 0.17.0
isodate >= 0.6.1
requests>=2.31.0  (optional: online)
```

### Observations

| Dépendance | Statut |
|---|---|
| `ingredient-parser-nlp` | Listée mais **non utilisée** — parseur custom `MultilingualIngredientParser` dans app.py |
| `recipe-scrapers>=15.0` (PyPI) | Le fork embarque `recipe_scrapers/` localement — privilégier `pip install -e .` sur o2switch |
| `werkzeug==3.0.1` | Version épinglée — vérifier compatibilité Flask>=2.0 |

---

## 6. Configuration o2switch (validée, non encore appliquée)

| Paramètre | Valeur |
|---|---|
| Application root | `/home/iwob6566/public_html/staging-api.mycookybook.com/mycookybook_api` |
| Startup file | `passenger_wsgi.py` |
| Entry point | `application` |

### Structure serveur requise

```
/home/iwob6566/public_html/staging-api.mycookybook.com/
├── recipe_scrapers/          # import local
├── mycookybook_api/          ← Passenger app root
│   └── passenger_wsgi.py
└── pyproject.toml
```

---

## 7. Fichiers créés (phase 1 — structure)

| Fichier | Statut |
|---|---|
| `mycookybook_api/__init__.py` | Créé |
| `mycookybook_api/templates/.gitkeep` | Créé |
| `mycookybook_api/static/.gitkeep` | Créé |
| `mycookybook_api/services/__init__.py` | Créé (vide) |
| `mycookybook_api/parsers/__init__.py` | Créé (vide) |
| `mycookybook_api/config/__init__.py` | Créé (vide) |
| `mycookybook_api/tests/__init__.py` | Créé (vide) |
| `deploy/README.md` | Créé |
| `deploy/staging.md` | Créé |
| `deploy/production.md` | Créé |
| `docs/MYCOOKYBOOK_MIGRATION_PLAN.md` | Créé |

---

## 8. Fichiers modifiés (phase 1)

**Aucun** — conformément aux contraintes :

- `app.py` : non modifié
- `passenger_wsgi.py` : non modifié
- Aucun import Python modifié
- Aucun fichier déplacé
- Aucun fichier supprimé

---

## 9. Fichiers déplacés

**Aucun** — pas de templates Flask existants à déplacer.

---

## 10. Risques identifiés

| # | Risque | Sévérité | Mitigation |
|---|---|---|---|
| 1 | **CRLF/LF** — ~2500 fichiers modifiés localement (fin de lignes) | Élevée | Normaliser avec `.gitattributes` avant Sync Fork |
| 2 | **Chemin JSON relatif** dans app.py (`open('units_multilingual_complete.json')`) | Élevée | Phase 2 : `Path(__file__).resolve().parent` |
| 3 | **Import recipe_scrapers** sur o2switch | Élevée | Clone complet + `pip install -e .` |
| 4 | **passenger_wsgi.py** import relatif `from app import app` | Moyenne | Phase 2 : `from mycookybook_api.app import app` + sys.path parent |
| 5 | **ingredient-parser-nlp** inutilisé | Faible | Retirer de requirements.txt en phase 2 |
| 6 | **Monolithe app.py** (1346 lignes) | Moyenne | Refactoriser vers services/parsers/config en phase 2 |
| 7 | **Pas de tests API** | Moyenne | Ajouter tests dans mycookybook_api/tests/ en phase 2 |
| 8 | **ingredients_multilingual_complete.json** non utilisé | Faible | Intégrer dans le parseur en phase 2 |

---

## 11. Actions recommandées

### Phase 1 — Structure (terminée)

- [x] Créer dossiers `templates/`, `static/`, `services/`, `parsers/`, `config/`, `tests/`
- [x] Créer `mycookybook_api/__init__.py`
- [x] Générer documentation `deploy/`
- [x] Générer ce rapport de migration
- [x] Aucun commit (conforme)
- [x] `app.py` et `passenger_wsgi.py` non modifiés (conforme)

### Phase 2 — Adaptations code (prochaine étape)

- [ ] Adapter `passenger_wsgi.py` :
  ```python
  REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  sys.path.insert(0, REPO_ROOT)
  from mycookybook_api.app import app
  application = app
  ```
- [ ] Corriger chemin JSON dans `app.py` via `Path(__file__)`
- [ ] Configurer Passenger sur o2switch staging
- [ ] Tester tous les endpoints

### Phase 3 — Refactorisation (future)

- [ ] Extraire `MultilingualIngredientParser` → `parsers/ingredient_parser.py`
- [ ] Extraire fonctions schema.org → `parsers/schema_org.py`
- [ ] Extraire routes → `services/scrape_service.py`, `services/parse_service.py`
- [ ] Centraliser config JSON → `config/data_paths.py`
- [ ] Intégrer `ingredients_multilingual_complete.json`
- [ ] Ajouter tests API dans `mycookybook_api/tests/`
- [ ] Retirer `ingredient-parser-nlp` des dépendances

### Phase 4 — Maintenance upstream

- [ ] Résoudre le problème CRLF (`.gitattributes` + reset)
- [ ] Sync Fork GitHub régulier
- [ ] Vérifier compatibilité après chaque sync

---

## 12. Stratégie de synchronisation upstream

```
hhursev/recipe-scrapers
        │
        │  Sync Fork (GitHub)
        ▼
neliville/recipe-scrapers-mycookybook
        │
        ├── recipe_scrapers/    ← mis à jour par sync
        ├── tests/              ← mis à jour par sync
        ├── docs/               ← mis à jour par sync (sauf MYCOOKYBOOK_MIGRATION_PLAN.md)
        ├── mycookybook_api/    ← jamais touché par upstream ✓
        └── deploy/             ← jamais touché par upstream ✓
```

Les dossiers MyCookyBook sont **hors périmètre upstream** — aucun conflit lors du Sync Fork.

---

## 13. Recommandations avant déploiement o2switch

1. **Terminer la phase 2** (adaptations `passenger_wsgi.py` et `app.py`)
2. Cloner le dépôt **complet** dans le répertoire du domaine
3. Créer un venv Python 3.10+ et installer :
   ```bash
   pip install -e .
   pip install -r mycookybook_api/requirements.txt
   ```
4. Configurer Passenger : app root = `mycookybook_api/`, startup = `passenger_wsgi.py`, entry = `application`
5. Tester avec curl sur staging avant production
6. Résoudre le problème CRLF avant tout Sync Fork
7. Valider staging → puis déployer production (voir `deploy/production.md`)

---

## 14. État passenger_wsgi.py actuel (inchangé)

```python
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

try:
    from app import app as application
except Exception as e:
    import traceback
    def application(environ, start_response):
        start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
        return [traceback.format_exc().encode()]
```

Fonctionne tant que le CWD est `mycookybook_api/` et que `recipe_scrapers` est installé dans le venv.

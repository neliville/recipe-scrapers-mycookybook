# Audit déploiement o2switch — MyCookyBook API

> Rapport généré le 20 juin 2026  
> Périmètre : analyse de `app.py`, `passenger_wsgi.py`, `requirements.txt`  
> Contrainte : **aucune modification de code** — préparation au premier déploiement staging

---

## 1. Résumé exécutif

| Critère | Verdict |
|---|---|
| Compatibilité Passenger | **Compatible** — entry point `application` conforme WSGI |
| Compatibilité Python 3.11 | **Compatible** — avec réserves sur `lxml==5.0` (binaire) |
| Déploiement staging immédiat (sans changement code) | **Possible** — avec contournement chemin JSON (voir §6) |
| Qualité parsing ingrédients au déploiement | **Dégradée** si JSON units non chargé |
| Recommandation Application root | **Option A — racine du dépôt** (voir §7) |

---

## 2. Analyse — `passenger_wsgi.py`

### Code actuel

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

### Compatibilité Passenger

| Point | Évaluation |
|---|---|
| Variable `application` | Conforme — Passenger cherche exactement ce nom |
| Protocole WSGI | Conforme — objet Flask WSGI callable |
| `sys.path.insert` | Correct — permet `from app import app` sans package installé |
| Gestion d'erreur au démarrage | Bonne — traceback en plain text si import échoue |
| Mode debug Flask | Non activé en production (`app.run` uniquement dans `__main__`) |

### Comportement selon Application root

| Configuration | Import `app` | CWD processus Passenger |
|---|---|---|
| Option A — root = racine dépôt, startup = `mycookybook_api/passenger_wsgi.py` | OK (sys.path) | **Racine du dépôt** (typique Passenger) |
| Option B — root = `mycookybook_api/`, startup = `passenger_wsgi.py` | OK | **`mycookybook_api/`** |

**Impact** : le CWD détermine si `open('units_multilingual_complete.json')` dans `app.py` réussit (voir §6).

---

## 3. Analyse — `app.py`

### Structure (1346 lignes, monolithique)

| Bloc | Lignes approx. | Contenu |
|---|---:|---|
| Utilitaires schema.org | 36–291 | `parse_iso_duration`, `extract_json_ld`, `scrape_with_enhanced_schema` |
| Parseur ingrédients | 298–936 | `Language`, `ParsedIngredient`, `MultilingualIngredientParser` |
| Application Flask | 943–1343 | 5 routes JSON |
| Dev local | 1345–1346 | `app.run(debug=True)` — **non exécuté sous Passenger** |

### Routes exposées

| Route | Méthodes | Dépendances runtime |
|---|---|---|
| `/` | GET | Flask uniquement |
| `/scrape` | GET, POST | `requests`, `recipe_scrapers`, `MultilingualIngredientParser`, schema.org |
| `/scrape-v2` | GET, POST | `requests`, `recipe_scrapers`, `extruct`, `w3lib` |
| `/parse-ingredient` | POST | `MultilingualIngredientParser` |
| `/parse-ingredients` | POST | `MultilingualIngredientParser` |

### Fichiers JSON

| Fichier | Chargé par app.py | Chemin utilisé | Risque |
|---|---|---|---|
| `units_multilingual_complete.json` | **Oui** (l.950) | `'units_multilingual_complete.json'` (relatif CWD) | **Élevé** |
| `ingredients_multilingual_complete.json` | **Non** | — | Aucun (présent mais inutilisé) |

```python
# app.py l.949-953
try:
    with open('units_multilingual_complete.json', 'r', encoding='utf-8') as f:
        units_data = json.load(f)
except Exception:
    units_data = []  # fallback silencieux — parsing dégradé
```

**Conséquence** : si le JSON n'est pas trouvé, l'API démarre sans erreur mais le parseur d'unités multilingues dynamiques est **désactivé** (patterns statiques uniquement).

### Appels réseau sortants

| Endpoint | HTTP sortant | Timeout |
|---|---|---|
| `/scrape` | `requests.get(url, timeout=20)` | 20 s |
| `/scrape-v2` | `requests.get(url, timeout=20)` | 20 s |
| `/parse-*` | Aucun | — |

**Prérequis o2switch** : le serveur doit autoriser les connexions HTTP/HTTPS sortantes ( généralement OK sur o2switch).

### Cloudflare (DNS déjà configurés)

| Domaine | Impact |
|---|---|
| `staging-api.mycookybook.com` | SSL/TLS mode **Full** ou **Full (strict)** recommandé cPanel |
| `api.mycookybook.com` | Idem |

Pas de modification code requise — vérifier le certificat SSL cPanel + mode Cloudflare.

---

## 4. Analyse — `requirements.txt`

### Contenu actuel

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

### Matrice import ↔ dépendance

| Import dans `app.py` | Package pip | Dans requirements.txt | Installé via |
|---|---|---|---|
| `flask` | Flask | ✓ | requirements.txt |
| `recipe_scrapers` | recipe-scrapers | ✓ | **`pip install -e .`** (fork local) |
| `requests` | requests | ✓ | requirements.txt |
| `extruct` | extruct | ✓ | requirements.txt |
| `w3lib` | w3lib | ✓ | requirements.txt |
| `bs4` | beautifulsoup4 | ✓ | requirements.txt |
| `re`, `json`, etc. | — (stdlib) | — | Python |

### Dépendances manquantes dans `requirements.txt`

| Package | Requis par | Impact si absent |
|---|---|---|
| **`isodate`** | `recipe_scrapers` (pyproject.toml upstream) | Installé via `pip install -e .` — OK si procédure respectée |
| **`lxml`** (indirect) | `extruct`, parsing HTML | Présent mais version **figée** `==5.0` |

> **Procédure obligatoire** : toujours exécuter `pip install -e .` **depuis la racine du clone** avant `pip install -r mycookybook_api/requirements.txt`. Installer uniquement `requirements.txt` sans `-e .` provoque `ModuleNotFoundError: recipe_scrapers`.

### Dépendances inutilisées dans `requirements.txt`

| Package | Import dans app.py | Verdict |
|---|---|---|
| **`ingredient-parser-nlp~=2.4.0`** | **Aucun** | **Inutilisé** — peut être retiré en phase 2 |

### Conflits de versions potentiels

| Package | requirements.txt | pyproject.toml upstream | Résolution pip |
|---|---|---|---|
| extruct | `>=0.16` | `>=0.17.0` | Prendra ≥0.17 |
| beautifulsoup4 | `>=4.9` | `>=4.12.3` | Prendra ≥4.12.3 |
| requests | `>=2.28` | `>=2.31.0` (optional online) | Prendra ≥2.28 |

Aucun conflit bloquant identifié.

---

## 5. Compatibilité Python 3.11

### Support déclaré

| Source | Version Python |
|---|---|
| `pyproject.toml` upstream | `>= 3.10` (classifiers 3.10–3.14) |
| o2switch | Python 3.10, 3.11, 3.12 disponibles via cPanel |

### Compatibilité par package (Python 3.11)

| Package | Python 3.11 | Note |
|---|---|---|
| Flask ≥2.0 | ✓ | — |
| werkzeug 3.0.1 | ✓ | — |
| recipe-scrapers ≥15.0 | ✓ | — |
| requests ≥2.28 | ✓ | — |
| beautifulsoup4 ≥4.9 | ✓ | — |
| **lxml 5.0** | ✓ | **Binaire C** — dépend de la compilation o2switch ; vérifier au premier `pip install` |
| extruct ≥0.16 | ✓ | — |
| w3lib ≥2.2 | ✓ | — |
| ingredient-parser-nlp | ✓ | Inutilisé |

**Recommandation version** : Python **3.11** sur o2switch — bon compromis support/stabilité.

**Point de vigilance** : `lxml==5.0` est épinglé. Si `pip install` échoue sur lxml (rare sur o2switch), tester `lxml>=5.0` sans pin en phase 2.

---

## 6. Risques de chemins relatifs

### Cartographie des chemins sensibles

| Chemin | Fichier | Option A (root = dépôt) | Option B (root = mycookybook_api) |
|---|---|---|---|
| `units_multilingual_complete.json` | app.py:950 | **Échec silencieux** (CWD = racine dépôt) | **OK** (CWD = mycookybook_api) |
| `from app import app` | passenger_wsgi.py | OK (sys.path) | OK (sys.path) |
| `from recipe_scrapers import scrape_html` | app.py:7 | OK (pip install -e .) | OK (pip install -e .) |
| `pip install -e .` | déploiement | OK (pyproject.toml à la racine) | OK (exécuté depuis parent) |

### Contournement sans modification de `app.py` (Option A)

Créer un lien symbolique à la racine du dépôt sur le serveur :

```bash
cd /home/iwob6566/public_html/staging-api.mycookybook.com
ln -sf mycookybook_api/units_multilingual_complete.json units_multilingual_complete.json
```

Permet le chargement JSON avec Option A **sans toucher au code Python**.

### Risques résiduels

| Risque | Sévérité | Mitigation |
|---|---|---|
| JSON units non chargé (fallback silencieux) | Élevée | Symlink (Option A) ou Option B ; test `/parse-ingredient` post-deploy |
| `ingredients_multilingual_complete.json` jamais utilisé | Faible | Phase 2 refactor |
| Logs `print()` avec emojis (✓, ✗, 🔍) | Faible | Visible dans logs Passenger ; pas bloquant |
| Timeout scrape 20s + latence Cloudflare | Moyenne | Configurer timeout Symfony ≥ 30s |

---

## 7. PHASE 2 — Option A vs Option B

### Option A — Application Root = racine du dépôt

```
/home/iwob6566/public_html/staging-api.mycookybook.com/   ← Application root
├── recipe_scrapers/
├── pyproject.toml
├── mycookybook_api/
│   └── passenger_wsgi.py   ← Startup file (chemin relatif)
└── units_multilingual_complete.json  ← symlink (contournement)
```

| Paramètre cPanel | Valeur |
|---|---|
| Application root | `/home/iwob6566/public_html/staging-api.mycookybook.com` |
| Startup file | `mycookybook_api/passenger_wsgi.py` |
| Entry point | `application` |

**Avantages**

- `pip install -e .` natif depuis le répertoire de déploiement
- `git pull` met à jour upstream + MyCookyBook en une commande
- Aligné avec la structure du fork et le Sync Fork GitHub
- Compatible avec un futur wrapper `passenger_wsgi.py` à la racine (phase 2)
- Logs et monitoring au niveau du déploiement complet

**Inconvénients**

- Chemin JSON relatif incompatible sans symlink ou correction code
- Startup file dans un sous-dossier — certains panels cPanel anciens peuvent rejeter (rare sur o2switch récent)

**Compatibilité Passenger** : ✓ — chemin relatif startup file supporté par Phusion Passenger / cPanel o2switch.

**Compatibilité Sync Fork** : ✓ — clone complet = modèle naturel du fork.

---

### Option B — Application Root = `mycookybook_api/`

```
/home/iwob6566/public_html/staging-api.mycookybook.com/
├── recipe_scrapers/          ← hors Application root, mais présent sur disque
├── pyproject.toml
└── mycookybook_api/          ← Application root Passenger
    ├── passenger_wsgi.py     ← Startup file
    ├── units_multilingual_complete.json  ← accessible via CWD
    └── app.py
```

| Paramètre cPanel | Valeur |
|---|---|
| Application root | `/home/iwob6566/public_html/staging-api.mycookybook.com/mycookybook_api` |
| Startup file | `passenger_wsgi.py` |
| Entry point | `application` |

**Avantages**

- Chemin JSON `units_multilingual_complete.json` **fonctionne immédiatement** sans contournement
- Configuration cPanel plus simple (startup file à la racine de l'app)
- `passenger_wsgi.py` actuel 100 % compatible

**Inconvénients**

- `pip install -e .` doit être lancé depuis le **parent** (une étape de plus, facile à oublier)
- Application root ne reflète pas la structure logique du fork
- `git pull` depuis le parent, mais Passenger ne voit que le sous-dossier
- Documentation déploiement fragmentée (racine clone vs app root)
- Migration future vers Option A nécessaire pour cohérence architecture

**Compatibilité Passenger** : ✓ — configuration classique et éprouvée.

**Compatibilité Sync Fork** : ✓ — le clone reste complet ; seule la config cPanel diffère.

---

### Recommandation unique

## → Option A — Application Root = racine du dépôt

**Justification**

1. **Architecture** : le fork est conçu comme un dépôt complet (upstream + couche MyCookyBook). L'Application root doit refléter cette réalité.
2. **Déploiement** : `pip install -e .` et `git pull` s'exécutent au même endroit — moins d'erreurs opérationnelles.
3. **Sync Fork** : workflow Git et déploiement serveur alignés sur la même arborescence.
4. **Évolution** : prépare la phase 2 (wrapper root, refactor modulaire) sans reconfiguration cPanel majeure.

**Prérequis staging sans modification de `app.py`** : créer le symlink JSON à la racine du dépôt (§6) avant les tests API.

**Prérequis staging long terme (phase 2 code)** : remplacer le chemin relatif par `Path(__file__).resolve().parent / 'units_multilingual_complete.json'` — correction de 1 ligne, hors scope actuel.

---

## 8. Risques de déploiement — synthèse

| # | Risque | Sévérité | Prob. | Mitigation |
|---|---|---|---|---|
| 1 | JSON units non chargé (parsing dégradé) | Élevée | Élevée (Option A sans symlink) | Symlink ou test post-deploy |
| 2 | `recipe_scrapers` non installé | Élevée | Moyenne | `pip install -e .` obligatoire |
| 3 | `lxml` échec compilation | Moyenne | Faible | Tester pip install ; assouplir pin |
| 4 | Timeout scrape (20s + réseau) | Moyenne | Moyenne | Timeout client Symfony ≥ 30s |
| 5 | SSL Cloudflare / cPanel | Moyenne | Faible | Mode Full ; certificat Let's Encrypt |
| 6 | Import error au démarrage | Élevée | Faible | Traceback dans `passenger_wsgi.py` fallback |
| 7 | `ingredient-parser-nlp` install inutile | Faible | Certaine | Retirer en phase 2 (allège venv) |
| 8 | Outbound HTTP bloqué | Élevée | Très faible | Tester `/scrape` post-deploy |
| 9 | Virtualenv non associé cPanel | Élevée | Moyenne | Vérifier association venv après création app |

---

## 9. Checklist pré-déploiement (audit)

- [x] `passenger_wsgi.py` exporte `application`
- [x] Routes Flask identifiées (5 endpoints)
- [x] Dépendances mappées import ↔ pip
- [x] `ingredient-parser-nlp` identifié comme inutilisé
- [x] `isodate` couvert par `pip install -e .`
- [x] Python 3.11 compatible
- [x] Risque chemin JSON documenté + contournement symlink
- [x] Option A vs B analysée — **Option A recommandée**
- [ ] Symlink JSON à créer sur serveur staging
- [ ] Procédure `pip install -e .` validée sur o2switch
- [ ] Tests API (voir `O2SWITCH_DEPLOYMENT_PLAN.md`)

---

## 10. Références

- [O2SWITCH_DEPLOYMENT_PLAN.md](O2SWITCH_DEPLOYMENT_PLAN.md) — plan de migration technique
- [deploy/o2switch-staging.md](../deploy/o2switch-staging.md) — procédure staging
- [MYCOOKYBOOK_MIGRATION_PLAN.md](MYCOOKYBOOK_MIGRATION_PLAN.md) — analyse initiale app.py

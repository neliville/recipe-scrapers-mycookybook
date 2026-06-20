# Déploiement o2switch — Staging

> Environnement : **staging-api.mycookybook.com**  
> Statut : document préparatoire — configuration Passenger **non encore appliquée**

---

## 1. Architecture recommandée

### Principe

Le dépôt Git complet est cloné à la racine du site. Passenger pointe sur **la racine du clone**, pas sur `mycookybook_api/` seul.

```
/home/iwob6566/public_html/staging-api.mycookybook.com/   ← Application root Passenger
├── recipe_scrapers/          # package upstream (requis pour les imports)
├── pyproject.toml            # requis pour pip install -e .
├── mycookybook_api/
│   ├── passenger_wsgi.py     # Startup file (chemin relatif depuis app root)
│   ├── app.py
│   ├── requirements.txt
│   ├── units_multilingual_complete.json
│   └── ...
├── deploy/
└── tests/
```

### Configuration Passenger (cPanel o2switch)

| Paramètre | Valeur |
|---|---|
| **Application root** | `/home/iwob6566/public_html/staging-api.mycookybook.com` |
| **Application URL** | `staging-api.mycookybook.com` |
| **Startup file** | `mycookybook_api/passenger_wsgi.py` |
| **Entry point** | `application` |
| **Python version** | 3.10+ |
| **Virtualenv** | `~/venv/staging-api` |

> **Note cPanel** : le champ « Startup file » accepte un chemin relatif à l'Application root.  
> Si cPanel n'accepte qu'un nom de fichier simple, voir la section 6 (wrapper root — phase 2).

---

## 2. Pourquoi Application root = racine du clone (et non `mycookybook_api/`)

| Critère | Racine du clone (recommandé) | `mycookybook_api/` seul (legacy) |
|---|---|---|
| `pip install -e .` | Fonctionne — `pyproject.toml` accessible | Échoue ou nécessite contournements |
| Import `recipe_scrapers` | Package installé depuis la racine | Nécessite manipulations sys.path |
| `git pull` / déploiement | Met à jour tout le dépôt proprement | Risque de désynchronisation |
| Sync Fork upstream | Cohérent avec la structure du fork | Clone partiel difficile à maintenir |
| Logs / monitoring | Vue globale du déploiement | Scope réduit, debug plus difficile |
| Évolution architecture | Permet un wrapper `passenger_wsgi.py` root | Bloqué dans un sous-dossier |

**Conclusion** : la racine du clone est l'Application root correcte. `mycookybook_api/` reste le **module applicatif**, pas la racine du déploiement.

Le `passenger_wsgi.py` actuel utilise `sys.path.insert(0, os.path.dirname(__file__))` et `from app import app` — il fonctionne tant que Passenger exécute le startup file **depuis** `mycookybook_api/` (CWD = ce dossier). Avec Application root = racine du clone, Passenger doit soit :

- pointer le startup file vers `mycookybook_api/passenger_wsgi.py` (cPanel le charge avec CWD = `mycookybook_api/`), **ou**
- utiliser un wrapper root en phase 2 (sans modifier le fichier existant).

---

## 3. Prérequis serveur

- Compte o2switch avec accès SSH et cPanel
- Python 3.10+ (requis par `pyproject.toml`)
- Git
- Domaine `staging-api.mycookybook.com` configuré

---

## 4. Installation initiale

### Étape 1 — Cloner le dépôt

```bash
ssh iwob6566@<serveur-o2switch>

mkdir -p /home/iwob6566/public_html/staging-api.mycookybook.com
cd /home/iwob6566/public_html/staging-api.mycookybook.com

git clone https://github.com/neliville/recipe-scrapers-mycookybook.git .
git checkout develop    # ou main selon la stratégie de déploiement staging
```

### Étape 2 — Environnement Python

```bash
python3.10 -m venv ~/venv/staging-api
source ~/venv/staging-api/bin/activate

pip install --upgrade pip

# Installer recipe_scrapers depuis le clone (OBLIGATOIRE depuis la racine)
pip install -e .

# Installer les dépendances API Flask
pip install -r mycookybook_api/requirements.txt
```

### Étape 3 — Configuration cPanel

1. cPanel → **Setup Python App** (Application Python)
2. Créer une nouvelle application :

| Champ | Valeur |
|---|---|
| Python version | 3.10+ |
| Application root | `/home/iwob6566/public_html/staging-api.mycookybook.com` |
| Application URL | `staging-api.mycookybook.com` |
| Application startup file | `mycookybook_api/passenger_wsgi.py` |
| Application Entry point | `application` |

3. Associer le virtualenv `~/venv/staging-api`
4. Cliquer **Restart**

### Étape 4 — Vérifications

```bash
# Endpoint racine
curl -s https://staging-api.mycookybook.com/ | python3 -m json.tool

# Scrape (URL de recette valide)
curl -s "https://staging-api.mycookybook.com/scrape?webUrl=https://www.marmiton.org/recettes/recette_risotto-aux-champignons.php"

# Parse ingrédient
curl -s -X POST https://staging-api.mycookybook.com/parse-ingredient \
  -H "Content-Type: application/json" \
  -d '{"ingredient": "200 g de farine", "language": "fr"}'
```

Réponse attendue sur `/` :

```json
{
  "service": "Recipe Scraper API",
  "version": "2.0 - Enhanced Schema.org",
  "endpoints": { ... }
}
```

---

## 5. Mise à jour (déploiement continu staging)

```bash
cd /home/iwob6566/public_html/staging-api.mycookybook.com
git pull origin develop
source ~/venv/staging-api/bin/activate
pip install -e .
pip install -r mycookybook_api/requirements.txt
# Redémarrer l'app Python dans cPanel → Restart
```

---

## 6. Alternative phase 2 — Wrapper root (si cPanel l'exige)

Si cPanel n'accepte pas un startup file dans un sous-dossier, créer **un nouveau** fichier à la racine (sans modifier `mycookybook_api/passenger_wsgi.py`) :

```python
# /home/iwob6566/public_html/staging-api.mycookybook.com/passenger_wsgi.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mycookybook_api'))
from passenger_wsgi import application  # re-export
```

Configuration cPanel dans ce cas :

| Paramètre | Valeur |
|---|---|
| Application root | `/home/iwob6566/public_html/staging-api.mycookybook.com` |
| Startup file | `passenger_wsgi.py` |
| Entry point | `application` |

---

## 7. Dépannage

| Symptôme | Cause probable | Action |
|---|---|---|
| 500 au démarrage | `recipe_scrapers` non installé | `pip install -e .` depuis la racine du clone |
| 500 au démarrage | JSON units introuvable | CWD ≠ `mycookybook_api/` — corriger `app.py` phase 2 (`Path(__file__)`) |
| ModuleNotFoundError Flask | venv non associé | Reconfigurer venv dans cPanel |
| ImportError app | Startup file mal configuré | Vérifier chemin `mycookybook_api/passenger_wsgi.py` |
| Timeout `/scrape` | Site cible lent | Normal ; consulter les logs |

---

## 8. Logs

```bash
# Logs Passenger (emplacement typique o2switch)
tail -f /home/iwob6566/public_html/staging-api.mycookybook.com/logs/passenger.log

# Logs stderr de l'application
tail -f /home/iwob6566/public_html/staging-api.mycookybook.com/mycookybook_api/stderr.log

# Logs cPanel
# cPanel → Metrics → Errors
```

---

## 9. Checklist premier déploiement staging

- [ ] Clone complet à la racine du site
- [ ] Branche `develop` (ou `main`) déployée
- [ ] `pip install -e .` exécuté depuis la racine
- [ ] `pip install -r mycookybook_api/requirements.txt`
- [ ] Application root = racine du clone (pas `mycookybook_api/`)
- [ ] Startup file = `mycookybook_api/passenger_wsgi.py`
- [ ] Entry point = `application`
- [ ] Virtualenv associé dans cPanel
- [ ] SSL actif (Let's Encrypt)
- [ ] Tests curl sur les 5 endpoints
- [ ] Logs sans erreur au démarrage

---

## 10. Références

- [deploy/staging.md](staging.md) — guide générique (approche legacy `mycookybook_api/` root)
- [docs/MYCOOKYBOOK_MIGRATION_PLAN.md](../docs/MYCOOKYBOOK_MIGRATION_PLAN.md)
- [docs/GIT_WORKFLOW.md](../docs/GIT_WORKFLOW.md) — stratégie staging → production

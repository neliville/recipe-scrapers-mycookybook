# Déploiement MyCookyBook API

Documentation de déploiement de l'API Flask MyCookyBook sur o2switch (Phusion Passenger).

## Vue d'ensemble

L'API MyCookyBook est isolée dans le dossier `mycookybook_api/` du fork
[neliville/recipe-scrapers-mycookybook](https://github.com/neliville/recipe-scrapers-mycookybook).
Elle s'appuie sur la bibliothèque upstream `recipe_scrapers/` sans la modifier.

| Environnement | Documentation |
|---|---|
| Staging | [staging.md](staging.md) |
| Production | [production.md](production.md) |

## Architecture serveur

```
/home/iwob6566/public_html/<domaine>/
├── recipe_scrapers/          # package upstream (import local ou pip install -e .)
├── mycookybook_api/          # ← Application root Passenger
│   ├── passenger_wsgi.py     # Startup file
│   ├── app.py
│   ├── requirements.txt
│   └── ...
└── pyproject.toml            # optionnel, pour pip install -e .
```

**Important** : Passenger pointe sur `mycookybook_api/` comme répertoire racine,
mais le clone Git complet (ou au minimum `recipe_scrapers/` + racine du dépôt)
doit être présent sur le serveur pour que `from recipe_scrapers import ...` fonctionne.

## Prérequis

- Python 3.10 ou supérieur (requis par `pyproject.toml` upstream)
- Accès SSH o2switch
- Application Python configurée dans cPanel o2switch
- Git

## Installation générale

```bash
# 1. Cloner le dépôt (racine du site, pas seulement mycookybook_api/)
cd /home/iwob6566/public_html/staging-api.mycookybook.com
git clone https://github.com/neliville/recipe-scrapers-mycookybook.git .

# 2. Créer un environnement virtuel
python3.10 -m venv ~/venv/staging-api
source ~/venv/staging-api/bin/activate

# 3. Installer recipe_scrapers depuis le fork local
pip install -e .

# 4. Installer les dépendances API
pip install -r mycookybook_api/requirements.txt
```

## Configuration Passenger (o2switch)

| Paramètre | Valeur |
|---|---|
| Application root | `.../mycookybook_api` |
| Startup file | `passenger_wsgi.py` |
| Entry point | `application` |
| Python | 3.10+ |

> **Note** : la configuration Passenger n'est pas encore appliquée.
> Voir [docs/MYCOOKYBOOK_MIGRATION_PLAN.md](../docs/MYCOOKYBOOK_MIGRATION_PLAN.md)
> pour les étapes restantes (adaptation de `passenger_wsgi.py`, correction des chemins JSON).

## Endpoints API

| Route | Méthode | Description |
|---|---|---|
| `/` | GET | Documentation JSON de l'API |
| `/scrape` | GET/POST | Scrape une recette (`webUrl`, `parse_ingredients`, `language`) |
| `/scrape-v2` | GET/POST | Scrape alternatif avec score qualité |
| `/parse-ingredient` | POST | Parse un ingrédient |
| `/parse-ingredients` | POST | Parse une liste d'ingrédients |

## Vérification post-déploiement

```bash
curl -s https://staging-api.mycookybook.com/ | python3 -m json.tool
curl -s "https://staging-api.mycookybook.com/scrape?webUrl=https://example.com/recipe"
```

## Logs

Sur o2switch, consulter les logs Passenger dans le répertoire de l'application :

- `passenger.log`
- `stderr.log`
- Logs cPanel → Erreurs du site

## Synchronisation upstream

Le dépôt reste synchronisable avec [hhursev/recipe-scrapers](https://github.com/hhursev/recipe-scrapers)
via le bouton **Sync Fork** GitHub. Les dossiers MyCookyBook (`mycookybook_api/`, `deploy/`)
ne sont jamais modifiés par l'upstream.

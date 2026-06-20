# Déploiement Staging — MyCookyBook API

Environnement de pré-production sur o2switch.

## Paramètres

| Paramètre | Valeur |
|---|---|
| Domaine | `staging-api.mycookybook.com` |
| Application root | `/home/iwob6566/public_html/staging-api.mycookybook.com/mycookybook_api` |
| Startup file | `passenger_wsgi.py` |
| Entry point | `application` |
| Branche Git | `main` |

## Étape 1 — Préparer le serveur

```bash
ssh iwob6566@<serveur-o2switch>

# Créer le répertoire si nécessaire
mkdir -p /home/iwob6566/public_html/staging-api.mycookybook.com
cd /home/iwob6566/public_html/staging-api.mycookybook.com

# Cloner ou mettre à jour le dépôt
git clone https://github.com/neliville/recipe-scrapers-mycookybook.git .
# ou : git pull origin main
```

## Étape 2 — Environnement Python

```bash
python3.10 -m venv ~/venv/staging-api
source ~/venv/staging-api/bin/activate

pip install --upgrade pip
pip install -e .
pip install -r mycookybook_api/requirements.txt
```

## Étape 3 — Configuration cPanel o2switch

1. Se connecter à cPanel o2switch
2. Aller dans **Setup Python App** (ou **Application Python**)
3. Créer une nouvelle application :

| Champ | Valeur |
|---|---|
| Python version | 3.10+ |
| Application root | `/home/iwob6566/public_html/staging-api.mycookybook.com/mycookybook_api` |
| Application URL | `staging-api.mycookybook.com` |
| Application startup file | `passenger_wsgi.py` |
| Application Entry point | `application` |

4. Associer le virtualenv créé à l'étape 2
5. Cliquer sur **Restart** après toute modification

> **Statut actuel** : cette configuration Passenger n'est **pas encore appliquée**.
> Des adaptations de code sont nécessaires avant le premier déploiement
> (voir [MYCOOKYBOOK_MIGRATION_PLAN.md](../docs/MYCOOKYBOOK_MIGRATION_PLAN.md)).

## Étape 4 — Vérifications

```bash
# Test endpoint racine
curl -s https://staging-api.mycookybook.com/

# Test scrape (remplacer par une URL de recette valide)
curl -s "https://staging-api.mycookybook.com/scrape?webUrl=https://www.marmiton.org/recettes/"

# Test parse ingrédient
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

## Étape 5 — Mise à jour

```bash
cd /home/iwob6566/public_html/staging-api.mycookybook.com
git pull origin main
source ~/venv/staging-api/bin/activate
pip install -e .
pip install -r mycookybook_api/requirements.txt
# Redémarrer l'app Python dans cPanel
```

## Dépannage

| Symptôme | Cause probable | Action |
|---|---|---|
| 500 au démarrage | Import `recipe_scrapers` échoué | Vérifier `pip install -e .` depuis la racine du clone |
| 500 au démarrage | Fichier JSON introuvable | Appliquer la correction `Path(__file__)` dans `app.py` (phase 2) |
| ModuleNotFoundError Flask | venv non associé | Reconfigurer le venv dans cPanel |
| Timeout sur `/scrape` | Site cible lent | Normal pour certains sites ; vérifier les logs |

## Logs

```bash
tail -f /home/iwob6566/public_html/staging-api.mycookybook.com/mycookybook_api/passenger.log
tail -f /home/iwob6566/public_html/staging-api.mycookybook.com/mycookybook_api/stderr.log
```

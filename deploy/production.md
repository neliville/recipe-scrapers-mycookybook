# Déploiement Production — MyCookyBook API

Environnement de production sur o2switch.

> **Statut** : document préparatoire. À compléter avant le go-live production.

## Paramètres

| Paramètre | Valeur |
|---|---|
| Domaine | `api.mycookybook.com` *(à confirmer)* |
| Application root | `/home/iwob6566/public_html/api.mycookybook.com/mycookybook_api` *(à confirmer)* |
| Startup file | `passenger_wsgi.py` |
| Entry point | `application` |
| Branche Git | `main` |

## Différences avec staging

| Aspect | Staging | Production |
|---|---|---|
| Domaine | `staging-api.mycookybook.com` | `api.mycookybook.com` |
| Virtualenv | `~/venv/staging-api` | `~/venv/production-api` |
| Debug Flask | Désactivé | Désactivé |
| Logs | Consultation libre | Monitoring régulier |

## Étape 1 — Préparer le serveur

```bash
ssh iwob6566@<serveur-o2switch>

mkdir -p /home/iwob6566/public_html/api.mycookybook.com
cd /home/iwob6566/public_html/api.mycookybook.com

git clone https://github.com/neliville/recipe-scrapers-mycookybook.git .
git checkout main
```

## Étape 2 — Environnement Python

```bash
python3.10 -m venv ~/venv/production-api
source ~/venv/production-api/bin/activate

pip install --upgrade pip
pip install -e .
pip install -r mycookybook_api/requirements.txt
```

## Étape 3 — Configuration cPanel o2switch

1. cPanel → **Setup Python App**
2. Créer l'application production :

| Champ | Valeur |
|---|---|
| Python version | 3.10+ |
| Application root | `/home/iwob6566/public_html/api.mycookybook.com/mycookybook_api` |
| Application URL | `api.mycookybook.com` |
| Application startup file | `passenger_wsgi.py` |
| Application Entry point | `application` |

3. Associer le virtualenv `~/venv/production-api`
4. Configurer le certificat SSL (Let's Encrypt via cPanel)

> **Statut actuel** : configuration Passenger **non encore appliquée**.
> Valider d'abord le staging avant de déployer en production.

## Étape 4 — Vérifications production

```bash
curl -s https://api.mycookybook.com/
curl -s "https://api.mycookybook.com/scrape?webUrl=<url-recette-test>"
curl -s -X POST https://api.mycookybook.com/parse-ingredient \
  -H "Content-Type: application/json" \
  -d '{"ingredient": "2 cuillères à soupe d huile", "language": "fr"}'
```

## Étape 5 — Mise à jour production

```bash
cd /home/iwob6566/public_html/api.mycookybook.com
git pull origin main
source ~/venv/production-api/bin/activate
pip install -e .
pip install -r mycookybook_api/requirements.txt
# Redémarrer l'app Python dans cPanel
```

## Checklist go-live

- [ ] Staging validé et stable
- [ ] Adaptations `passenger_wsgi.py` et `app.py` appliquées (phase 2)
- [ ] Domaine production configuré dans cPanel
- [ ] SSL actif
- [ ] Virtualenv production créé et associé
- [ ] Tests curl sur tous les endpoints
- [ ] Logs Passenger sans erreur au démarrage
- [ ] Problème CRLF résolu avant Sync Fork

## Dépannage

Identique au staging — voir [staging.md](staging.md#dépannage).

## Rollback

```bash
cd /home/iwob6566/public_html/api.mycookybook.com
git log --oneline -5
git checkout <commit-stable>
source ~/venv/production-api/bin/activate
pip install -e .
# Redémarrer l'app Python dans cPanel
```

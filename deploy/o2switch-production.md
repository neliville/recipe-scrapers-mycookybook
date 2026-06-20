# Déploiement o2switch — Production

> Environnement : **api.mycookybook.com**  
> Statut : document préparatoire — **ne pas déployer avant validation staging complète**

---

## 1. Architecture recommandée

Identique au staging : **Application root = racine du clone Git**, pas `mycookybook_api/` seul.

```
/home/iwob6566/public_html/api.mycookybook.com/   ← Application root Passenger
├── recipe_scrapers/
├── pyproject.toml
├── mycookybook_api/
│   ├── passenger_wsgi.py     ← Startup file (relatif à app root)
│   ├── app.py
│   └── ...
└── ...
```

### Configuration Passenger (cPanel o2switch)

| Paramètre | Valeur |
|---|---|
| **Application root** | `/home/iwob6566/public_html/api.mycookybook.com` |
| **Application URL** | `api.mycookybook.com` |
| **Startup file** | `mycookybook_api/passenger_wsgi.py` |
| **Entry point** | `application` |
| **Python version** | 3.10+ |
| **Virtualenv** | `~/venv/production-api` |
| **Branche Git** | `main` |

---

## 2. Pourquoi Application root = racine du clone

Voir la justification détaillée dans [o2switch-staging.md](o2switch-staging.md#2-pourquoi-application-root--racine-du-clone-et-non-mycookybook_api).

Résumé :

1. **`pip install -e .`** nécessite `pyproject.toml` à la racine — impossible si Application root = `mycookybook_api/`.
2. **`from recipe_scrapers import ...`** dans `app.py` requiert le package installé depuis le clone complet.
3. **`git pull`** met à jour upstream + MyCookyBook en une seule opération.
4. **Sync Fork** reste cohérent avec la structure du dépôt GitHub.
5. **Évolution** : un wrapper `passenger_wsgi.py` root peut être ajouté en phase 2 sans toucher au code existant.

L'approche legacy (Application root = `.../mycookybook_api`) documentée dans [production.md](production.md) est **déconseillée** pour les raisons ci-dessus.

---

## 3. Différences staging vs production

| Aspect | Staging | Production |
|---|---|---|
| Domaine | `staging-api.mycookybook.com` | `api.mycookybook.com` |
| Application root | `/home/iwob6566/public_html/staging-api.mycookybook.com` | `/home/iwob6566/public_html/api.mycookybook.com` |
| Branche Git | `develop` | `main` |
| Virtualenv | `~/venv/staging-api` | `~/venv/production-api` |
| Validation | Tests libres, itérations fréquentes | Checklist go-live stricte |
| Rollback | `git checkout` rapide | Tag release + procédure documentée |

---

## 4. Prérequis go-live

- [ ] Staging validé et stable pendant au moins une semaine
- [ ] Tous les endpoints curl passent sur staging
- [ ] Correction chemin JSON dans `app.py` (phase 2) — recommandé avant prod
- [ ] `.gitattributes` commité
- [ ] Problème CRLF résolu (fait)
- [ ] Branche `main` contient la release validée depuis `develop`

---

## 5. Installation initiale production

### Étape 1 — Préparer le serveur

```bash
ssh iwob6566@<serveur-o2switch>

mkdir -p /home/iwob6566/public_html/api.mycookybook.com
cd /home/iwob6566/public_html/api.mycookybook.com

git clone https://github.com/neliville/recipe-scrapers-mycookybook.git .
git checkout main
```

### Étape 2 — Environnement Python

```bash
python3.10 -m venv ~/venv/production-api
source ~/venv/production-api/bin/activate

pip install --upgrade pip
pip install -e .
pip install -r mycookybook_api/requirements.txt
```

### Étape 3 — Configuration cPanel

1. cPanel → **Setup Python App**
2. Créer l'application production :

| Champ | Valeur |
|---|---|
| Python version | 3.10+ |
| Application root | `/home/iwob6566/public_html/api.mycookybook.com` |
| Application URL | `api.mycookybook.com` |
| Application startup file | `mycookybook_api/passenger_wsgi.py` |
| Application Entry point | `application` |

3. Associer le virtualenv `~/venv/production-api`
4. Configurer SSL (Let's Encrypt via cPanel)
5. **Restart**

### Étape 4 — Vérifications production

```bash
curl -s https://api.mycookybook.com/ | python3 -m json.tool

curl -s "https://api.mycookybook.com/scrape?webUrl=<url-recette-test>"

curl -s -X POST https://api.mycookybook.com/parse-ingredient \
  -H "Content-Type: application/json" \
  -d '{"ingredient": "2 cuillères à soupe d huile", "language": "fr"}'

curl -s -X POST https://api.mycookybook.com/parse-ingredients \
  -H "Content-Type: application/json" \
  -d '{"ingredients": ["200 g farine", "3 oeufs"], "language": "fr"}'
```

---

## 6. Mise à jour production

```bash
cd /home/iwob6566/public_html/api.mycookybook.com
git pull origin main
source ~/venv/production-api/bin/activate
pip install -e .
pip install -r mycookybook_api/requirements.txt
# Redémarrer l'app Python dans cPanel → Restart
```

**Recommandation** : toujours valider la même version sur staging (`develop`) avant de merger vers `main` et déployer en production.

---

## 7. Stratégie staging → production

```
develop (staging)  ──merge + tag──►  main (production)
       │                                    │
       └── staging-api.mycookybook.com      └── api.mycookybook.com
```

| Action | Commande / procédure |
|---|---|
| Valider sur staging | Tests curl + monitoring logs |
| Merger vers main | `git checkout main && git merge develop` |
| Tagger la release | `git tag -a v2.x.x -m "Production release"` |
| Déployer prod | `git pull origin main` sur le serveur production |
| Rollback | `git checkout v2.x.x-1` + restart Passenger |

Voir [docs/GIT_WORKFLOW.md](../docs/GIT_WORKFLOW.md) pour le détail du workflow Git.

---

## 8. Rollback

```bash
cd /home/iwob6566/public_html/api.mycookybook.com

# Identifier le tag stable précédent
git tag -l 'v*'
git log --oneline -5

# Revenir au tag stable
git checkout v2.0.0

source ~/venv/production-api/bin/activate
pip install -e .
pip install -r mycookybook_api/requirements.txt

# Redémarrer l'app Python dans cPanel
```

---

## 9. Dépannage

Identique au staging — voir [o2switch-staging.md](o2switch-staging.md#7-dépannage).

Points spécifiques production :

| Symptôme | Action |
|---|---|
| Pic de trafic / timeout | Vérifier logs Passenger ; envisager cache ou rate limiting (phase future) |
| Erreur après Sync Fork | Rollback vers tag stable ; ne pas déployer directement après sync sans tests staging |
| SSL expiré | Renouveler via cPanel → SSL/TLS |

---

## 10. Checklist go-live production

- [ ] Staging stable ≥ 1 semaine
- [ ] Merge `develop` → `main` effectué
- [ ] Tag release créé (`v2.x.x`)
- [ ] Clone production à la racine `/home/iwob6566/public_html/api.mycookybook.com`
- [ ] Application root = racine du clone
- [ ] Startup file = `mycookybook_api/passenger_wsgi.py`
- [ ] Entry point = `application`
- [ ] Virtualenv production créé et associé
- [ ] SSL actif sur `api.mycookybook.com`
- [ ] Tests curl sur les 5 endpoints
- [ ] Logs Passenger sans erreur
- [ ] Monitoring post-déploiement (24h)

---

## 11. Références

- [deploy/o2switch-staging.md](o2switch-staging.md)
- [deploy/production.md](production.md) — guide legacy
- [docs/MYCOOKYBOOK_ROADMAP.md](../docs/MYCOOKYBOOK_ROADMAP.md)
- [docs/GIT_WORKFLOW.md](../docs/GIT_WORKFLOW.md)

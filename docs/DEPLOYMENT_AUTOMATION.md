# Déploiement automatique — GitHub Actions → o2switch staging

> Déclenchement : `git push origin develop`  
> Cible : `https://staging-api.mycookybook.com`

---

## Architecture

```
git push develop
       │
       ▼
GitHub Actions (.github/workflows/deploy-staging.yml)
       │  SSH
       ▼
o2switch — scripts/deploy-staging.sh
       │  git pull + pip install + touch tmp/restart.txt
       ▼
Passenger redémarre l'application Flask
```

| Élément | Chemin / valeur |
|---|---|
| Repository serveur | `/home/iwob6566/apps/recipe-scrapers-mycookybook` |
| Virtualenv | `/home/iwob6566/virtualenv/apps/recipe-scrapers-mycookybook/3.11` |
| Startup file Passenger | `mycookybook_api/passenger_wsgi.py` |
| Entry point | `application` |
| Script de déploiement | `scripts/deploy-staging.sh` |

---

## Secrets GitHub requis

Configurer dans **GitHub → Settings → Secrets and variables → Actions → New repository secret**.

| Secret | Exemple | Description |
|---|---|---|
| `O2SWITCH_HOST` | `outils-qualite.com` | Hostname SSH o2switch |
| `O2SWITCH_USER` | `iwob6566` | Utilisateur SSH |
| `O2SWITCH_PORT` | `22` | Port SSH (vérifier dans cPanel si différent) |
| `O2SWITCH_SSH_KEY` | clé privée OpenSSH | Clé **dédiée CI** — ne jamais utiliser votre clé personnelle |
| `O2SWITCH_API_TOKEN` | token cPanel | Token API cPanel (Manage API Tokens) — **requis** pour whitelist pare-feu o2switch |
| `O2SWITCH_OTP_SECRET` | *(optionnel)* | Secret OTP si la 2FA est activée sur le compte o2switch |

> **Pare-feu o2switch** : par défaut, le port SSH 22 n'accepte que les IP whitelistées. GitHub Actions utilise des IP dynamiques ; le workflow appelle `d9beuD/o2switch-whitelisting` avant le déploiement SSH. Sans `O2SWITCH_API_TOKEN`, la connexion SSH échoue avec `i/o timeout`.

### Créer le token API cPanel

1. cPanel → **Manage API Tokens** → **Create**
2. Nom : `github-actions-deploy-staging`
3. Copier le token → secret `O2SWITCH_API_TOKEN`

---

## Générer une clé SSH dédiée CI

Sur votre poste local :

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy-staging" -f ~/.ssh/o2switch_github_actions -N ""
```

- **Clé publique** (`~/.ssh/o2switch_github_actions.pub`) → à ajouter sur le serveur
- **Clé privée** (`~/.ssh/o2switch_github_actions`) → contenu complet dans le secret `O2SWITCH_SSH_KEY`

Sur le serveur o2switch :

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo "<contenu de o2switch_github_actions.pub>" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

Vérifier la connexion depuis votre poste (avec la clé CI) :

```bash
ssh -i ~/.ssh/o2switch_github_actions -p 22 iwob6566@outils-qualite.com 'echo SSH OK'
```

---

## Bootstrap (une fois, avant le 1er workflow)

Le script de déploiement doit exister sur le serveur avant que GitHub Actions puisse l'exécuter.

```bash
ssh iwob6566@outils-qualite.com

cd /home/iwob6566/apps/recipe-scrapers-mycookybook
git pull origin develop
chmod +x scripts/deploy-staging.sh
bash scripts/deploy-staging.sh
```

Attendu en fin de script : `DEPLOY SUCCESS`

---

## Tester le workflow

1. Configurer les 4 secrets GitHub (voir ci-dessus)
2. Pousser un commit sur `develop` :

   ```bash
   git push origin develop
   ```

3. GitHub → **Actions** → workflow **Deploy Staging**
4. Vérifier les logs du job : présence de `DEPLOY SUCCESS`
5. Lancer les tests smoke depuis votre poste :

   ```bash
   bash scripts/run-staging-api-tests.sh
   ```

   Attendu : **10/10 tests passés**.

---

## Rollback

### Rollback rapide sur le serveur

```bash
ssh iwob6566@outils-qualite.com

cd /home/iwob6566/apps/recipe-scrapers-mycookybook
git log --oneline -5                    # identifier le commit stable
git checkout develop
git reset --hard <commit_stable>

source /home/iwob6566/virtualenv/apps/recipe-scrapers-mycookybook/3.11/bin/activate
pip install -r mycookybook_api/requirements.txt
pip install -e .
mkdir -p tmp && touch tmp/restart.txt
```

Puis depuis votre poste :

```bash
bash scripts/run-staging-api-tests.sh
```

### Rollback durable (recommandé)

Préférer `git revert` sur `develop` puis `git push origin develop` pour éviter une divergence entre GitHub et le serveur. Le workflow redéploiera automatiquement la version revertée.

---

## Dépannage

| Symptôme | Cause probable | Action |
|---|---|---|
| `Permission denied (publickey)` | Clé absente ou mauvaise dans `authorized_keys` / secret | Vérifier clé publique serveur et secret `O2SWITCH_SSH_KEY` |
| `dial tcp ... i/o timeout` | IP runner GitHub non whitelistée (pare-feu o2switch) | Configurer `O2SWITCH_API_TOKEN` ; vérifier l'étape « Whitelist runner IP » |
| `bash: .../deploy-staging.sh: No such file` | Bootstrap non fait | `git pull` + `chmod +x` manuel sur le serveur |
| `git pull` échoue | Credentials Git absents sur le serveur | Vérifier clone SSH ou token HTTPS |
| Workflow timeout | `pip install` lent | Augmenter `timeout-minutes` dans le workflow |
| API 500 après deploy | Import Python cassé | Consulter logs Passenger ; relancer le script manuellement |

---

## Liens croisés

- [O2SWITCH_DEPLOYMENT_PLAN.md](O2SWITCH_DEPLOYMENT_PLAN.md) — déploiement manuel complet
- [deploy/o2switch-staging.md](../deploy/o2switch-staging.md) — architecture Passenger staging
- [scripts/run-staging-api-tests.sh](../scripts/run-staging-api-tests.sh) — batterie de tests post-déploiement

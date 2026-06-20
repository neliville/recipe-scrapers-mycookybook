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
       │  1. Whitelist IP runner (API cPanel + mot de passe)
       │  2. SSH + deploy-staging.sh
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
| `O2SWITCH_HOST` | `iwob6566.odns.fr` | Hostname cPanel / SSH o2switch |
| `O2SWITCH_USER` | `iwob6566` | Utilisateur cPanel / SSH |
| `O2SWITCH_PORT` | `22` | Port SSH |
| `O2SWITCH_SSH_KEY` | clé privée OpenSSH | Clé **dédiée CI** (contenu complet du fichier `.pem` / clé privée) |
| `O2SWITCH_CPANEL_PASSWORD` | mot de passe cPanel | Mot de passe **cPanel** (pas le mot de passe SSH) — whitelist pare-feu |
| `O2SWITCH_KEEP_IPS` | `176.149.102.163,77.133.249.81` | IP personnelles à **ne jamais supprimer** lors du déploiement CI |

> **Pare-feu o2switch** : seules les IP whitelistées peuvent se connecter en SSH. GitHub Actions utilise des IP dynamiques. Le workflow appelle l'[API Autorisation SSH o2switch](https://faq.o2switch.fr/cpanel/outils/exception-parefeu/) avec le mot de passe cPanel avant chaque déploiement, supprime les anciennes IP CI et ajoute l'IP du runner courant, sans toucher aux IP listées dans `O2SWITCH_KEEP_IPS`.

### Alternative : token API cPanel

Si **Manage API Tokens** fonctionne un jour, vous pouvez revenir à un token API (`O2SWITCH_API_TOKEN`) au lieu du mot de passe. L'implémentation actuelle utilise le mot de passe car l'interface token est inaccessible sur certains comptes o2switch.

---

## Générer une clé SSH dédiée CI

Sur votre poste local :

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy-staging" -f ~/.ssh/o2switch_github_actions -N ""
```

- **Clé publique** → ajouter dans cPanel **SSH Access** (Autoriser) ou dans `~/.ssh/authorized_keys`
- **Clé privée** → secret `O2SWITCH_SSH_KEY`

Vérifier la connexion :

```bash
ssh -i ~/.ssh/o2switch_github_actions iwob6566@iwob6566.odns.fr 'echo SSH OK'
```

---

## Configurer les secrets (commandes)

```bash
gh secret set O2SWITCH_HOST -b "iwob6566.odns.fr" -R neliville/recipe-scrapers-mycookybook
gh secret set O2SWITCH_USER -b "iwob6566" -R neliville/recipe-scrapers-mycookybook
gh secret set O2SWITCH_PORT -b "22" -R neliville/recipe-scrapers-mycookybook
gh secret set O2SWITCH_KEEP_IPS -b "176.149.102.163,77.133.249.81" -R neliville/recipe-scrapers-mycookybook
gh secret set O2SWITCH_CPANEL_PASSWORD -R neliville/recipe-scrapers-mycookybook
# coller le mot de passe cPanel quand demandé
gh secret set O2SWITCH_SSH_KEY < ~/.ssh/o2switch_github_actions -R neliville/recipe-scrapers-mycookybook
```

---

## Bootstrap (une fois, avant le 1er workflow)

```bash
ssh iwob6566@iwob6566.odns.fr
cd /home/iwob6566/apps/recipe-scrapers-mycookybook
git pull origin develop
chmod +x scripts/deploy-staging.sh
bash scripts/deploy-staging.sh
```

Attendu : `DEPLOY SUCCESS`

---

## Tester le workflow

1. Configurer tous les secrets (dont `O2SWITCH_CPANEL_PASSWORD` et `O2SWITCH_KEEP_IPS`)
2. `git push origin develop`
3. GitHub → **Actions** → **Deploy Staging** → logs : `Whitelist OK` puis `DEPLOY SUCCESS`
4. `bash scripts/run-staging-api-tests.sh` → **10/10**

---

## Rollback

### Rollback rapide sur le serveur

```bash
ssh iwob6566@iwob6566.odns.fr
cd /home/iwob6566/apps/recipe-scrapers-mycookybook
git log --oneline -5
git checkout develop
git reset --hard <commit_stable>
source /home/iwob6566/virtualenv/apps/recipe-scrapers-mycookybook/3.11/bin/activate
pip install -r mycookybook_api/requirements.txt
pip install -e .
mkdir -p tmp && touch tmp/restart.txt
```

### Rollback durable

`git revert` sur `develop` + `git push origin develop` — le workflow redéploie automatiquement.

---

## Dépannage

| Symptôme | Cause probable | Action |
|---|---|---|
| `curl: (22) HTTP 401` | Mauvais mot de passe cPanel | Vérifier `O2SWITCH_CPANEL_PASSWORD` (cPanel, pas SSH) |
| `dial tcp ... i/o timeout` | Whitelist échouée ou pas propagée | Vérifier logs étape « Whitelist runner IP » ; attendre 65 s |
| `Permission denied (publickey)` | Clé SSH CI incorrecte | Vérifier `O2SWITCH_SSH_KEY` + clé autorisée dans cPanel SSH Access |
| Plus d'accès SSH perso | IP personnelle supprimée par erreur | Vérifier `O2SWITCH_KEEP_IPS` ; réajouter via cPanel **Autorisation SSH** |
| Quota 5/5 exceptions | Trop d'IP CI accumulées | Le workflow supprime les IP hors `O2SWITCH_KEEP_IPS` avant d'ajouter la runner |

---

## Liens croisés

- [Autorisation SSH o2switch (FAQ)](https://faq.o2switch.fr/cpanel/outils/exception-parefeu/)
- [O2SWITCH_DEPLOYMENT_PLAN.md](O2SWITCH_DEPLOYMENT_PLAN.md)
- [scripts/run-staging-api-tests.sh](../scripts/run-staging-api-tests.sh)

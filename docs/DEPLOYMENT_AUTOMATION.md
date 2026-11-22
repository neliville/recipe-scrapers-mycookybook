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
       │  1. Session cPanel sur O2SWITCH_CPANEL_HOST, TLS vérifié
       │  2. Ajout du runner seulement s'il reste une place
       │  3. Confirmation de son adresse, puis attente du port SSH
       │  4. SSH vers O2SWITCH_HOST + deploy-staging.sh
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
| `O2SWITCH_HOST` | `iwob6566.odns.fr` | Nom utilisé pour le SSH. Il ne sert pas à l'appel cPanel. |
| `O2SWITCH_CPANEL_HOST` | `yellow.o2switch.net` | Nom TLS du cPanel, port 2083. Le certificat est vérifié. |
| `O2SWITCH_USER` | `iwob6566` | Utilisateur cPanel / SSH |
| `O2SWITCH_PORT` | `22` | Port SSH |
| `O2SWITCH_SSH_KEY` | clé privée OpenSSH | Clé **dédiée CI** (contenu complet du fichier `.pem` / clé privée) |
| `O2SWITCH_CPANEL_PASSWORD` | mot de passe cPanel | Mot de passe **cPanel** (pas le mot de passe SSH) — ouverture de session |
| `O2SWITCH_KEEP_IPS` | `176.149.102.163,77.133.249.81` | Adresses administratives à préserver lors d'un nettoyage manuel |

> **Pare-feu o2switch** : seules les IP autorisées peuvent se connecter en SSH. GitHub Actions utilise des IP dynamiques. Le workflow ouvre une session cPanel par `POST /login/?login_only=1`, puis lit la whitelist. Il n'appelle jamais `r=remove`.

## Whitelist SSH

Le quota o2switch est de 5 exceptions. Une entrée compte pour une adresse, même si elle existe en entrée et en sortie.

| Situation | Comportement |
|---|---|
| L'adresse du runner est déjà autorisée | Aucune modification |
| Il reste au moins une place | Ajout de cette adresse seulement |
| Le quota est plein | Arrêt du déploiement, message `manual_cleanup_required` |
| L'ajout ou la confirmation échoue | Arrêt avant le SSH |

Aucune adresse SSH n'est supprimée automatiquement. Une adresse absente de `O2SWITCH_KEEP_IPS` peut appartenir à un autre projet ou à un accès administratif : ce n'est pas une adresse obsolète.

Si un nettoyage manuel est nécessaire, le faire dans cPanel **Autorisation SSH** et conserver :

- les adresses de `O2SWITCH_KEEP_IPS` ;
- les accès administratifs ;
- les adresses utilisées par les autres projets hébergés sur le même compte.

Le SSH ne démarre qu'après une relecture qui confirme la présence du runner. L'attente suivante teste seulement l'ouverture du port, au plus 12 fois, avec un délai de connexion de 8 secondes. L'authentification reste celle de la clé `O2SWITCH_SSH_KEY`.

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
gh secret set O2SWITCH_CPANEL_HOST -b "yellow.o2switch.net" -R neliville/recipe-scrapers-mycookybook
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
3. GitHub → **Actions** → **Deploy Staging** → logs : `action=already_present` ou `action=add`, puis `whitelist_confirmed=yes`, puis `DEPLOY SUCCESS`
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

### Point de retour avant recipe-scrapers 15.14.0

Le serveur staging sert le commit `a3e8a242`. La sauvegarde locale hors dépôt est `backups/staging-pre-15.14.0-2026-11-22/` (`server-state.txt` et `pip-freeze.txt`). Un retour arrière doit remettre ce commit et ce gel pip, puis recréer `tmp/restart.txt`. Il faut aussi revenir en arrière sur `origin/develop`, sinon le déploiement suivant réinstalle la 15.14.0.

### Rollback durable

`git revert` sur `develop` + `git push origin develop` — le workflow redéploie automatiquement.

---

## Dépannage

| Symptôme | Cause probable | Action |
|---|---|---|
| `TLS_ERROR` ou `curl: (60)` | Le nom `O2SWITCH_CPANEL_HOST` ne correspond pas au certificat | Corriger le secret. Ne pas désactiver la vérification TLS. |
| `manual_cleanup_required` | Quota de 5 exceptions déjà atteint | Libérer une place à la main, sans retirer une adresse administrative ou utilisée par un autre projet, puis relancer |
| `ssh_port_unavailable` | Le port SSH ne s'ouvre pas dans le délai | Ne pas relancer en boucle. Vérifier que l'adresse du runner a bien été confirmée. |
| `Permission denied (publickey)` | Clé SSH CI incorrecte | Vérifier `O2SWITCH_SSH_KEY` + clé autorisée dans cPanel SSH Access |
| Plus d'accès SSH perso | Adresse retirée par un nettoyage manuel | La réajouter via cPanel **Autorisation SSH**. Le workflow ne retire aucune adresse. |

---

## Liens croisés

- [Autorisation SSH o2switch (FAQ)](https://faq.o2switch.fr/cpanel/outils/exception-parefeu/)
- [O2SWITCH_DEPLOYMENT_PLAN.md](O2SWITCH_DEPLOYMENT_PLAN.md)
- [scripts/run-staging-api-tests.sh](../scripts/run-staging-api-tests.sh)

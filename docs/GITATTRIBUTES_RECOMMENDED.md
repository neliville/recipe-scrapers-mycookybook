# Proposition `.gitattributes` — MyCookyBook

> Ce document propose le contenu d'un fichier `.gitattributes` pour le fork MyCookyBook.  
> **Le fichier réel n'existe pas encore dans le dépôt** — à créer manuellement.

---

## 1. État actuel

| Élément | Statut |
|---|---|
| Fichier `.gitattributes` dans le dépôt | **Absent** |
| Problème CRLF | **Résolu** (nettooyage effectué) |
| Config Git WSL | `core.autocrlf input`, `core.eol lf` |

Sans `.gitattributes`, Git ne force pas la normalisation EOL au niveau du dépôt. Le risque de récidive CRLF existe lors d'un clone sous Windows ou avant un Sync Fork.

---

## 2. Contenu recommandé

Créer manuellement un fichier `.gitattributes` à la **racine du dépôt** avec le contenu suivant :

```gitattributes
# Normalisation des fins de ligne — MyCookyBook fork
# Voir docs/GITATTRIBUTES_RECOMMENDED.md

* text=auto

# Langages et formats texte — forcer LF
*.py          text eol=lf
*.yml         text eol=lf
*.yaml        text eol=lf
*.md          text eol=lf
*.json        text eol=lf
*.sh          text eol=lf
*.toml        text eol=lf
*.cfg         text eol=lf
*.ini         text eol=lf
*.rst         text eol=lf
*.html        text eol=lf
*.testhtml    text eol=lf

# Fichiers binaires — ne pas toucher
*.png         binary
*.jpg         binary
*.jpeg        binary
*.gif         binary
*.ico         binary
*.woff        binary
*.woff2       binary
```

---

## 3. Explication ligne par ligne

| Règle | Effet |
|---|---|
| `* text=auto` | Git détecte automatiquement les fichiers texte vs binaires |
| `*.py text eol=lf` | Tous les fichiers Python normalisés en LF à la prochaine réécriture |
| `*.json text eol=lf` | Important pour `tests/test_data/` (~2400 fichiers JSON) |
| `*.testhtml text eol=lf` | Fichiers HTML de test upstream |
| `*.png binary` etc. | Empêche la corruption d'assets binaires |

---

## 4. Procédure d'ajout (manuelle)

```bash
# 1. Créer le fichier à la racine du dépôt
#    (copier le contenu de la section 2)

# 2. Vérifier l'impact sans committer
git add --dry-run .gitattributes

# 3. Commiter séparément (commit dédié)
git add .gitattributes
git commit -m "Add .gitattributes for LF normalization"

# 4. Vérifier qu'aucun faux positif CRLF n'apparaît
git status --short
git ls-files --eol recipe_scrapers/__init__.py
# Attendu : i/lf w/lf attr/text eol=lf
```

---

## 5. Impact attendu

| Scénario | Comportement |
|---|---|
| Clone sous WSL/Linux | LF en working tree — OK |
| Clone sous Windows + `autocrlf input` | LF en index, LF en working tree — OK |
| Sync Fork upstream | Upstream n'a pas `.gitattributes` ; notre fichier s'applique localement |
| Nouveau fichier `.py` | Automatiquement LF grâce à `eol=lf` |

**Attention** : l'ajout de `.gitattributes` peut provoquer une réécriture EOL au prochain `git add` sur les fichiers concernés. Faire ce commit **sur un dépôt déjà nettoyé** (état actuel) pour minimiser le bruit.

---

## 6. Relation avec la configuration Git globale

| Config | Valeur | Rôle |
|---|---|---|
| `core.autocrlf` | `input` | Convertit CRLF → LF à l'index, pas de conversion à l'écriture |
| `core.eol` | `lf` | Fin de ligne par défaut pour fichiers texte sans attribut |
| `.gitattributes` | `eol=lf` | Force LF indépendamment de la config locale |

Les trois éléments se complètent. `.gitattributes` est la protection la plus fiable au niveau dépôt.

---

## 7. Ce qu'il ne faut PAS faire

- Ne pas utiliser `core.autocrlf true` sous WSL (reconvertit en CRLF)
- Ne pas committer `.gitattributes` en même temps que 2500 fichiers re-normalisés
- Ne pas supprimer `.gitattributes` après Sync Fork — il protège le fork

---

## 8. Vérification post-ajout

```bash
# Attribut appliqué
git check-attr eol -- recipe_scrapers/__init__.py
# Attendu : recipe_scrapers/__init__.py: eol: lf

# EOL cohérent
git ls-files --eol recipe_scrapers/__init__.py mycookybook_api/app.py
# Attendu : i/lf w/lf attr/text eol=lf pour les deux

# Pas de diff sémantique
git diff --ignore-space-at-eol
# Attendu : vide
```

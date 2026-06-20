#!/usr/bin/env bash
#
# git-cleanup.sh — Nettoyage CRLF phantom pour recipe-scrapers-mycookybook
#
# Ce script :
#   1. Sauvegarde les 17 fichiers MyCookyBook
#   2. Restaure l'arbre de travail depuis l'index (git restore --worktree .)
#   3. Vérifie l'intégrité des fichiers MyCookyBook
#   4. Restaure depuis le backup si perte détectée
#
# Ce script NE FAIT PAS :
#   - git clean
#   - git reset --hard
#   - git commit
#   - git push
#
# Usage : bash scripts/git-cleanup.sh
# Prérequis : exécuter scripts/git-config-recommended.sh avant (recommandé)
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BACKUP_DIR="/tmp/mycookybook-backup-$(date +%Y%m%d-%H%M%S)"

# ---------------------------------------------------------------------------
# Fichiers MyCookyBook à préserver (17 chemins)
# ---------------------------------------------------------------------------
MYCOOKYBOOK_PATHS=(
    "deploy/README.md"
    "deploy/staging.md"
    "deploy/production.md"
    "docs/MYCOOKYBOOK_MIGRATION_PLAN.md"
    "mycookybook_api/__init__.py"
    "mycookybook_api/app.py"
    "mycookybook_api/passenger_wsgi.py"
    "mycookybook_api/requirements.txt"
    "mycookybook_api/README.md"
    "mycookybook_api/ingredients_multilingual_complete.json"
    "mycookybook_api/units_multilingual_complete.json"
    "mycookybook_api/templates/.gitkeep"
    "mycookybook_api/static/.gitkeep"
    "mycookybook_api/services/__init__.py"
    "mycookybook_api/parsers/__init__.py"
    "mycookybook_api/config/__init__.py"
    "mycookybook_api/tests/__init__.py"
)

# Fichiers untracked MyCookyBook — doivent survivre au restore
MYCOOKYBOOK_UNTRACKED=(
    "deploy/README.md"
    "deploy/staging.md"
    "deploy/production.md"
    "docs/MYCOOKYBOOK_MIGRATION_PLAN.md"
    "mycookybook_api/__init__.py"
    "mycookybook_api/templates/.gitkeep"
    "mycookybook_api/static/.gitkeep"
    "mycookybook_api/services/__init__.py"
    "mycookybook_api/parsers/__init__.py"
    "mycookybook_api/config/__init__.py"
    "mycookybook_api/tests/__init__.py"
)

# ---------------------------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------------------------
info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*" >&2; }
error() { echo "[ERROR] $*" >&2; exit 1; }

count_modified() {
    git status --short | grep -v '^??' | wc -l | tr -d ' '
}

count_untracked() {
    git status --short | grep '^??' | wc -l | tr -d ' '
}

# ---------------------------------------------------------------------------
# Phase 0 — Confirmation interactive
# ---------------------------------------------------------------------------
echo "============================================================"
echo "  Nettoyage Git CRLF — MyCookyBook"
echo "  Dépôt : $REPO_ROOT"
echo "============================================================"
echo ""
info "État actuel :"
info "  Fichiers modified  : $(count_modified)"
info "  Fichiers untracked : $(count_untracked)"
echo ""
warn "Cette opération va exécuter : git restore --worktree ."
warn "Les ~2519 faux positifs CRLF seront annulés."
warn "Les fichiers untracked MyCookyBook ne seront PAS supprimés."
echo ""
read -r -p "Continuer ? (tapez 'oui' pour confirmer) : " CONFIRM
if [[ "$CONFIRM" != "oui" ]]; then
    info "Opération annulée."
    exit 0
fi

# ---------------------------------------------------------------------------
# Phase 1 — Sauvegarde MyCookyBook
# ---------------------------------------------------------------------------
info "Phase 1 — Sauvegarde des fichiers MyCookyBook dans : $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

BACKED_UP=0
for path in "${MYCOOKYBOOK_PATHS[@]}"; do
    if [[ -e "$path" ]]; then
        dest_dir="$BACKUP_DIR/$(dirname "$path")"
        mkdir -p "$dest_dir"
        cp -a "$path" "$dest_dir/"
        BACKED_UP=$((BACKED_UP + 1))
    else
        warn "Fichier absent (ignoré) : $path"
    fi
done
info "  $BACKED_UP / ${#MYCOOKYBOOK_PATHS[@]} fichiers sauvegardés."

# ---------------------------------------------------------------------------
# Phase 2 — Nettoyage CRLF (tracked only)
# ---------------------------------------------------------------------------
info "Phase 2 — Restauration de l'arbre de travail (git restore --worktree .)"
git restore --worktree .

# ---------------------------------------------------------------------------
# Phase 3 — Vérifications
# ---------------------------------------------------------------------------
info "Phase 3 — Vérifications post-nettoyage"

MODIFIED_AFTER=$(count_modified)
UNTRACKED_AFTER=$(count_untracked)

info "  Fichiers modified  après restore : $MODIFIED_AFTER"
info "  Fichiers untracked après restore : $UNTRACKED_AFTER"

if [[ "$MODIFIED_AFTER" -gt 0 ]]; then
    warn "Des fichiers modified subsistent :"
    git status --short | grep -v '^??' || true
fi

# Vérifier que les untracked MyCookyBook sont présents
MISSING=()
for path in "${MYCOOKYBOOK_UNTRACKED[@]}"; do
    if [[ ! -e "$path" ]]; then
        MISSING+=("$path")
    fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
    warn "Fichiers MyCookyBook untracked manquants détectés — restauration depuis backup."
    for path in "${MISSING[@]}"; do
        src="$BACKUP_DIR/$path"
        if [[ -e "$src" ]]; then
            dest_dir="$(dirname "$path")"
            mkdir -p "$dest_dir"
            cp -a "$src" "$path"
            info "  Restauré : $path"
        else
            error "Impossible de restaurer $path — absent du backup $src"
        fi
    done
else
    info "  Tous les fichiers untracked MyCookyBook sont intacts."
fi

# Vérification diff sémantique
DIFF_LINES=$(git diff --ignore-space-at-eol | wc -l | tr -d ' ')
if [[ "$DIFF_LINES" -eq 0 ]]; then
    info "  git diff --ignore-space-at-eol : aucune différence (OK)"
else
    warn "  git diff --ignore-space-at-eol : $DIFF_LINES lignes — vérifier manuellement."
fi

# ---------------------------------------------------------------------------
# Résumé final
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  Nettoyage terminé"
echo "============================================================"
info "Backup conservé dans : $BACKUP_DIR"
info "Fichiers modified restants  : $(count_modified) (attendu : 0)"
info "Fichiers untracked restants : $(count_untracked) (attendu : ~11 MyCookyBook)"
echo ""
info "Prochaines étapes manuelles :"
info "  1. git status --short          # vérifier l'état"
info "  2. git add deploy/ docs/MYCOOKYBOOK_MIGRATION_PLAN.md mycookybook_api/..."
info "  3. git commit                  # commit MyCookyBook uniquement"
info "  4. Optionnel : ajouter .gitattributes (voir docs/GIT_CLEANUP_PLAN.md)"
echo ""
info "Consultez docs/GIT_CLEANUP_PLAN.md pour la checklist complète."

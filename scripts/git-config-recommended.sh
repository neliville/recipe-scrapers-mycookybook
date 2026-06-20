#!/usr/bin/env bash
#
# git-config-recommended.sh — Configuration Git recommandée pour WSL/Linux
#
# Configure core.autocrlf=input pour éviter la conversion CRLF dans
# l'arbre de travail sous WSL.
#
# Usage : bash scripts/git-config-recommended.sh
#
# Note : modifie la configuration Git GLOBALE (--global).
#        Pour une config locale au dépôt uniquement, remplacer --global par --local.
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*" >&2; }

echo "============================================================"
echo "  Configuration Git recommandée — LF/CRLF"
echo "  Dépôt : $REPO_ROOT"
echo "============================================================"
echo ""

# ---------------------------------------------------------------------------
# État actuel
# ---------------------------------------------------------------------------
info "Configuration actuelle :"
CURRENT=$(git config --global --get core.autocrlf 2>/dev/null || echo "(non définie)")
info "  core.autocrlf (global) : $CURRENT"

LOCAL=$(git config --local --get core.autocrlf 2>/dev/null || echo "(non définie)")
info "  core.autocrlf (local)  : $LOCAL"
echo ""

# ---------------------------------------------------------------------------
# Application de la configuration recommandée
# ---------------------------------------------------------------------------
info "Application : git config --global core.autocrlf input"
git config --global core.autocrlf input

NEW=$(git config --global --get core.autocrlf)
info "  core.autocrlf (global) : $NEW"
echo ""

# ---------------------------------------------------------------------------
# Vérifications
# ---------------------------------------------------------------------------
info "Vérifications :"
echo ""

info "1. core.autocrlf"
if [[ "$NEW" == "input" ]]; then
    info "   OK — core.autocrlf = input"
else
    warn "   ATTENTION — valeur inattendue : $NEW (attendu : input)"
fi
echo ""

info "2. EOL d'un fichier upstream (recipe_scrapers/__init__.py)"
if git ls-files --eol recipe_scrapers/__init__.py 2>/dev/null; then
    EOL=$(git ls-files --eol recipe_scrapers/__init__.py 2>/dev/null)
    if echo "$EOL" | grep -q 'w/crlf'; then
        warn "   Working tree encore en CRLF — exécuter scripts/git-cleanup.sh"
        warn "   Attendu après nettoyage : i/lf w/lf"
    elif echo "$EOL" | grep -q 'w/lf'; then
        info "   OK — working tree en LF"
    else
        info "   Résultat : $EOL"
    fi
else
    warn "   Fichier non trouvé dans l'index Git"
fi
echo ""

info "3. Nombre de fichiers dans git status --short"
STATUS_COUNT=$(git status --short | wc -l | tr -d ' ')
MODIFIED_COUNT=$(git status --short | grep -v '^??' | wc -l | tr -d ' ')
UNTRACKED_COUNT=$(git status --short | grep '^??' | wc -l | tr -d ' ')
info "   Total     : $STATUS_COUNT"
info "   Modified  : $MODIFIED_COUNT (attendu : 0 après git-cleanup.sh)"
info "   Untracked : $UNTRACKED_COUNT (attendu : ~11 MyCookyBook après nettoyage)"
echo ""

info "4. Diff sémantique (ignore-space-at-eol)"
DIFF_LINES=$(git diff --ignore-space-at-eol 2>/dev/null | wc -l | tr -d ' ')
if [[ "$DIFF_LINES" -eq 0 ]]; then
    info "   OK — aucune différence sémantique"
else
    warn "   $DIFF_LINES lignes de diff — probablement CRLF si modified > 0"
fi
echo ""

# ---------------------------------------------------------------------------
# Résumé
# ---------------------------------------------------------------------------
echo "============================================================"
echo "  Configuration appliquée"
echo "============================================================"
info "core.autocrlf = input (global)"
echo ""
info "Prochaine étape : bash scripts/git-cleanup.sh"
info "Documentation   : docs/GIT_CLEANUP_PLAN.md"
echo ""
warn "Si vous travaillez aussi sous Windows natif (hors WSL),"
warn "ne pas utiliser core.autocrlf=true — préférer WSL + input,"
warn "ou un .gitattributes avec eol=lf (voir GIT_CLEANUP_PLAN.md)."

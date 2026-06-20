#!/usr/bin/env bash
#
# run-staging-api-tests.sh — Batterie de tests API staging MyCookyBook
# Usage : bash scripts/run-staging-api-tests.sh [BASE_URL]
#
set -euo pipefail

BASE="${1:-https://staging-api.mycookybook.com}"
PASS=0
FAIL=0

ok()   { echo "[PASS] $*"; PASS=$((PASS + 1)); }
fail() { echo "[FAIL] $*" >&2; FAIL=$((FAIL + 1)); }

check_http() {
    local url="$1" expected="$2" label="$3"
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 "$url")
    if [[ "$code" == "$expected" ]]; then ok "$label (HTTP $code)"; else fail "$label — attendu $expected, reçu $code"; fi
}

check_json_field() {
    local url="$1" method="$2" data="$3" field="$4" label="$5"
    local resp val
    if [[ "$method" == "POST" ]]; then
        resp=$(curl -s --max-time 30 -X POST "$url" -H "Content-Type: application/json" -d "$data")
    else
        resp=$(curl -s --max-time 30 "$url")
    fi
    val=$(echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d${field})" 2>/dev/null || echo "ERROR")
    if [[ "$val" == "True" ]] || [[ "$val" == "true" ]] || [[ -n "$val" && "$val" != "ERROR" && "$val" != "None" && "$val" != "False" ]]; then
        ok "$label"
    else
        fail "$label — réponse: $(echo "$resp" | head -c 200)"
    fi
}

echo "============================================================"
echo "  Tests API — $BASE"
echo "============================================================"

check_http "$BASE/" 200 "GET /"
check_json_field "$BASE/" GET "" "['service']" "GET / — service présent"

# Parse ingrédient grammes
resp=$(curl -s --max-time 30 -X POST "$BASE/parse-ingredient" \
    -H "Content-Type: application/json" \
    -d '{"ingredient": "200 g de farine", "language": "fr"}')
unit=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('unit',''))" 2>/dev/null || echo "")
if [[ "$unit" == "g" ]]; then ok "POST /parse-ingredient — unité g"; else fail "POST /parse-ingredient — unit='$unit'"; fi

# Parse cuillères (JSON units dynamiques)
resp=$(curl -s --max-time 30 -X POST "$BASE/parse-ingredient" \
    -H "Content-Type: application/json" \
    -d '{"ingredient": "2 cuillères à soupe d huile d olive", "language": "fr"}')
unit=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('unit',''))" 2>/dev/null || echo "")
if [[ -n "$unit" ]]; then ok "POST /parse-ingredient — unités JSON ($unit)"; else fail "POST /parse-ingredient — unité vide (JSON non chargé?)"; fi

check_http "$BASE/scrape" 400 "GET /scrape sans webUrl"
check_http "$BASE/parse-ingredient" 400 "POST /parse-ingredient sans body" 
# Note: curl POST sans body peut retourner 400 ou 415 selon config

# Scrape Marmiton (URL test upstream)
MARMITON_URL="https://www.marmiton.org/recettes/recette_ratatouille_23223.aspx"
resp=$(curl -s --max-time 45 "$BASE/scrape?webUrl=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$MARMITON_URL'))")&language=fr")
success=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success',False))" 2>/dev/null || echo "False")
if [[ "$success" == "True" ]]; then ok "GET /scrape Marmiton"; else fail "GET /scrape Marmiton — $(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('message','')[:80])" 2>/dev/null)"; fi

echo ""
echo "============================================================"
echo "  Résultat : $PASS passés, $FAIL échoués"
echo "============================================================"
[[ "$FAIL" -eq 0 ]]

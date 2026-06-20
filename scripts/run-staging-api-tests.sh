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

resp=$(curl -s -w "\nHTTP:%{http_code}" --max-time 30 -X POST "$BASE/parse-ingredient" \
    -H "Content-Type: application/json" -d '{}')
code=$(echo "$resp" | grep HTTP | cut -d: -f2)
if [[ "$code" == "400" ]]; then ok "POST /parse-ingredient sans ingredient (HTTP 400)"; else fail "POST /parse-ingredient body vide — attendu 400, reçu $code"; fi

# Scrape Marmiton (URL test upstream)
MARMITON_URL="https://www.marmiton.org/recettes/recette_ratatouille_23223.aspx"
resp=$(curl -s --max-time 45 "$BASE/scrape?webUrl=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$MARMITON_URL'))")&language=fr")
success=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success',False))" 2>/dev/null || echo "False")
if [[ "$success" == "True" ]]; then ok "GET /scrape Marmiton"; else fail "GET /scrape Marmiton — $(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('message','')[:80])" 2>/dev/null)"; fi

# Parse ingrédients 750g — régression partitifs FR
resp=$(curl -s --max-time 30 -X POST "$BASE/parse-ingredients" \
  -H "Content-Type: application/json" \
  -d '{"ingredients": ["15 cl d'\''eau", "1 filet d'\''huile d'\''olive", "Ras el-hanout"], "language": "fr"}')
eau=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['ingredients'][0]['ingredient'])" 2>/dev/null || echo "")
huile=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['ingredients'][1]['ingredient'])" 2>/dev/null || echo "")
ras=$(echo "$resp" | python3 -c "import sys,json; i=json.load(sys.stdin)['data']['ingredients'][2]; print(i['ingredient'], i['unit'])" 2>/dev/null || echo "")
if [[ "$eau" == "eau" && "$huile" == "huile d'olive" ]]; then ok "POST /parse-ingredients FR partitifs (eau, huile d'olive)"; else fail "POST /parse-ingredients FR — eau='$eau' huile='$huile'"; fi
if echo "$ras" | grep -q "Ras el-hanout"; then ok "POST /parse-ingredients épice sans quantité (Ras el-hanout)"; else fail "POST /parse-ingredients Ras el-hanout — $ras"; fi

# Scrape 750g (/scrape — régression anti-bot)
G750_URL="https://www.750g.com/cuisses-de-poulet-et-pomme-de-terre-au-four-r79431.htm"
resp=$(curl -s --max-time 45 "$BASE/scrape?webUrl=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$G750_URL'))")&language=fr")
success=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success',False))" 2>/dev/null || echo "False")
title=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('title',''))" 2>/dev/null || echo "")
if [[ "$success" == "True" && -n "$title" ]]; then ok "GET /scrape 750g (title=$title)"; else fail "GET /scrape 750g — $(echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('message',''), d.get('data',{}).get('title',''))" 2>/dev/null)"; fi

echo ""
echo "============================================================"
echo "  Résultat : $PASS passés, $FAIL échoués"
echo "============================================================"
[[ "$FAIL" -eq 0 ]]

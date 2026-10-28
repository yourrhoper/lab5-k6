#!/usr/bin/env bash
# Последовательный прогон load → stress → spike со свежим стендом перед каждым тестом.
set -u
cd "$(dirname "$0")"
mkdir -p results
for P in load stress spike; do
  pkill -f "[n]ode server/server.js" 2>/dev/null; sleep 1
  node server/server.js > "results/server-$P.log" 2>&1 &
  sleep 2
  K6_NO_USAGE_REPORT=true K6_WEB_DASHBOARD=true K6_WEB_DASHBOARD_PORT=-1 K6_WEB_DASHBOARD_EXPORT="results/$P-dashboard.html" \
  k6 run -e PROFILE=$P \
    --out csv="results/$P.csv.gz" \
    --summary-export="results/$P-summary.json" \
    k6/achievements-test.js > "results/$P-console.txt" 2>&1
  echo "$P exit code: $?" >> results/exit-codes.txt
done
pkill -f "[n]ode server/server.js"
echo DONE >> results/exit-codes.txt

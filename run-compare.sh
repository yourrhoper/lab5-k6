#!/usr/bin/env bash
# Бонус: сравнение двух версий стенда под stress-профилем (HASH_MODE=async).
set -u
cd "$(dirname "$0")"
mkdir -p results
pkill -f "[n]ode server/server.js" 2>/dev/null; sleep 1
HASH_MODE=async node server/server.js > results/server-stress-async.log 2>&1 &
sleep 2
K6_NO_USAGE_REPORT=true k6 run -e PROFILE=stress --out csv=results/stress-async.csv.gz \
  --summary-export=results/stress-async-summary.json k6/achievements-test.js > results/stress-async-console.txt 2>&1
echo "stress-async exit code: $?" >> results/exit-codes.txt
pkill -f "[n]ode server/server.js"
echo COMPARE-DONE >> results/exit-codes.txt

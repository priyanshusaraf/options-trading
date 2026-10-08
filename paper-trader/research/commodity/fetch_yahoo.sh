#!/bin/bash
# Fetch the Yahoo Finance inputs: USDINR daily (10y) for the rupee conversion, and
# 60m NYMEX futures (~2y, Yahoo's limit) for the independent cross-check.
D=${COMMODITY_DATA:-$(cd "$(dirname "$0")" && pwd)/data}
mkdir -p "$D/yahoo"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
for s in "INR=X:1d:10y" "NG=F:60m:730d" "CL=F:60m:730d" "GC=F:60m:730d" "SI=F:60m:730d"; do
  IFS=: read -r sym iv rg <<<"$s"
  curl -s -A "$UA" "https://query1.finance.yahoo.com/v8/finance/chart/$sym?interval=$iv&range=$rg" \
       -o "$D/yahoo/${sym}_${iv}.json"
  echo "$sym $iv $(wc -c < "$D/yahoo/${sym}_${iv}.json") bytes"
  sleep 2
done

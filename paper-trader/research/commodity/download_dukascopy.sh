#!/bin/bash
D=${COMMODITY_DATA:-$(cd "$(dirname "$0")" && pwd)/data}
BIN=${DUKASCOPY_BIN:-npx -y dukascopy-node@1.50.0}
for inst in gascmdusd xauusd xagusd lightcmdusd; do
  for y in 2019 2020 2021 2022 2023 2024 2025 2026; do
    to="$((y+1))-01-01"; [ $y = 2026 ] && to="2026-10-07"
    for attempt in 1 2 3; do
      $BIN -i $inst -from $y-01-01 -to $to -t m5 -f csv -v true -dir $D/raw/$inst -fn ${inst}_$y -r 3 -bs 10 -bp 500 > $D/raw/log_${inst}_$y.txt 2>&1 && break
      sleep 5
    done
    echo "$inst $y done $(wc -l < $D/raw/$inst/${inst}_$y.csv 2>/dev/null)"
  done
done
echo ALLDONE

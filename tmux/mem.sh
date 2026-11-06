#!/bin/sh
# メモリ使用率を表示
if [ "$(uname)" = Darwin ]; then
  # macOS には available が無いので、アプリ + 固定 + 圧縮 を搭載量で割る
  vm_stat | awk -v total="$(sysctl -n hw.memsize)" '
  /page size of/ { ps = $8 }
  /^Anonymous pages/ { anon = $3 }
  /^Pages purgeable/ { purg = $3 }
  /^Pages wired down/ { wired = $4 }
  /^Pages occupied by compressor/ { comp = $5 }
  END { printf "%d%%\n", (anon - purg + wired + comp) * ps / total * 100 }'
else
  # total - available
  free | awk '/^Mem:/{printf "%d%%\n", ($2-$7)/$2*100}'
fi

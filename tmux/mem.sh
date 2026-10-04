#!/bin/sh
# メモリ使用率（total - available）を表示
free | awk '/^Mem:/{printf "%d%%\n", ($2-$7)/$2*100}'

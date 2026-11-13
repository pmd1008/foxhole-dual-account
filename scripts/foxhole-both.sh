#!/bin/bash
# Запустить оба аккаунта сразу: сначала основной (порт 57343), затем второй (57344).
set -u
DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
run() { if [ -x "$DIR/$1" ]; then "$DIR/$1"; else "$DIR/$1.sh"; fi; }
run foxhole-main
sleep 10
run foxhole-alt

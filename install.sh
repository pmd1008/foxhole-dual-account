#!/bin/bash
# Установка: лаунчеры Steam-аккаунтов, ярлыки меню, обработчик ввода
# (автокликер/привязки) и конфиг по умолчанию.
#
#   ./install.sh                 — всё, кроме MPX-демонов
#   ./install.sh --with-mpx      — плюс seat2-start и seat2-focuspin
#   ./install.sh --shim          — плюс сборка LD_PRELOAD-шима для второго HOME
#   PREFIX=/usr/local ./install.sh
set -eu

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${PREFIX:-/usr/local}"
BIN="$PREFIX/bin"
DESKTOP="${DESKTOP_DIR:-$HOME/.local/share/applications}"
CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/foxhole-dual"
ALT_HOME="${FOXHOLE_ALT_HOME:-$HOME/steam-alt}"

WITH_MPX=0
WITH_SHIM=0
for a in "$@"; do
  case "$a" in
    --with-mpx) WITH_MPX=1 ;;
    --shim) WITH_SHIM=1 ;;
  esac
done

install -d "$BIN" "$DESKTOP" "$CONFIG"

# --- Steam-аккаунты ---------------------------------------------------------
install -m 0755 "$DIR/scripts/foxhole-main.sh" "$BIN/foxhole-main"
install -m 0755 "$DIR/scripts/foxhole-alt.sh"  "$BIN/foxhole-alt"
install -m 0755 "$DIR/scripts/foxhole-both.sh" "$BIN/foxhole-both"
install -m 0644 "$DIR/desktop/foxhole-main.desktop" "$DESKTOP/"
install -m 0644 "$DIR/desktop/foxhole-alt.desktop"  "$DESKTOP/"
install -m 0644 "$DIR/desktop/foxhole-both.desktop" "$DESKTOP/"

# --- Ввод: автокликер и привязки -------------------------------------------
install -m 0755 "$DIR/scripts/foxhole-input" "$BIN/foxhole-input"
if [ ! -f "$CONFIG/devices.conf" ]; then
  install -m 0644 "$DIR/config/devices.conf" "$CONFIG/devices.conf"
  echo "устройства: $CONFIG/devices.conf (правьте: foxhole-input setup)"
fi
if [ ! -f "$CONFIG/input.toml" ]; then
  install -m 0644 "$DIR/config/input.toml" "$CONFIG/input.toml"
  echo "конфиг: $CONFIG/input.toml"
else
  echo "конфиг уже есть: $CONFIG/input.toml (не трогаю)"
fi

# --- MPX (второе место ввода) ----------------------------------------------
if [ "$WITH_MPX" = 1 ]; then
  install -m 0755 "$DIR/mpx/seat2-start"       "$BIN/seat2-start"
  install -m 0755 "$DIR/mpx/seat2-focuspin.py" "$BIN/seat2-focuspin"
  install -m 0755 "$DIR/mpx/seat2-cp.py"       "$BIN/seat2-cp"
  install -m 0755 "$DIR/mpx/seat2-layoutd.py"  "$BIN/seat2-layoutd"
  install -d "$DESKTOP"
  # автозапуск при входе в Plasma X11
  cat > "$DESKTOP/seat2-mpx.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Second seat (MPX)
Comment=Вторая пара клавиатура+мышь для двух окон Foxhole
Exec=$BIN/seat2-start
X-KDE-autostart-after=panel
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF
  chmod 0644 "$DESKTOP/seat2-mpx.desktop"
fi

if [ "$WITH_SHIM" = 1 ]; then
  install -d "$ALT_HOME"
  gcc -shared -fPIC -O2 -DALT_HOME="\"$ALT_HOME\"" \
      -o "$ALT_HOME/libhomealt.so" "$DIR/shim/homealt.c" -ldl
  echo "шим собран: $ALT_HOME/libhomealt.so"
  echo "пропишите в Launch Options игры:"
  echo "  LD_PRELOAD=$ALT_HOME/libhomealt.so %command%"
fi

command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || true
echo "готово: $BIN/foxhole-{main,alt,both}, foxhole-input; ярлыки в $DESKTOP"
echo
echo "дальше:"
echo "  foxhole-input doctor          # проверить uinput / evdev / XInput2"
echo "  foxhole-input run             # автокликер и привязки (или автозапуск)"
echo "  foxhole-both                  # оба аккаунта"
echo "не забудьте отдельный префикс игры для второго клиента:"
echo "  mkdir -p \"$ALT_HOME/.local/share/Steam/steamapps/compatdata/505460-alt\""
echo "  Launch Options: STEAM_COMPAT_DATA_PATH=\"$ALT_HOME/.local/share/Steam/steamapps/compatdata/505460-alt\" %command%"

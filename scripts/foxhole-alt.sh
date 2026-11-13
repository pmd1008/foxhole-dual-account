#!/bin/bash
# Foxhole — второй Steam-аккаунт.
#
# Ключевой момент: у второго клиента должен быть СВОЙ IPC-порт.
# По умолчанию Steam слушает 127.0.0.1:57343; второй клиент на том же порту
# приводит к тому, что его игры обслуживает первый клиент (чужой аккаунт).
#
# Настройки можно переопределить переменными окружения:
#   FOXHOLE_ALT_HOME  — HOME второго клиента   (по умолчанию $HOME/steam-alt)
#   FOXHOLE_ALT_PORT  — IPC-порт второго клиента (по умолчанию 57344)
#   FOXHOLE_USER      — пользователь сессии     (по умолчанию владелец $HOME)
#   FOXHOLE_APPID     — AppID игры              (по умолчанию 505460)
set -u

APPID="${FOXHOLE_APPID:-505460}"
if [ -z "${FOXHOLE_USER:-}" ]; then
  if [ "$(id -u)" = 0 ]; then U=pmd; else U=$(id -un); fi
else U="$FOXHOLE_USER"; fi
USER_HOME=$(getent passwd "$U" | cut -d: -f6)
A="${FOXHOLE_ALT_HOME:-$USER_HOME/steam-alt}"
PORT="${FOXHOLE_ALT_PORT:-57344}"
RT="${XDG_RUNTIME_DIR:-/run/user/$(id -u "$U")}"

# DISPLAY/XAUTHORITY берём из живой сессии (хардкод ломается при перезаходе:
# имя xauth-файла меняется, Steam падает с «Check your DISPLAY environment variable»).
if [ "$(id -u)" = 0 ]; then
  eval "$(runuser -u "$U" -- env XDG_RUNTIME_DIR="$RT" systemctl --user show-environment 2>/dev/null \
          | sed -nE 's/^(DISPLAY|XAUTHORITY|WAYLAND_DISPLAY)=(.*)$/export \1="\2"/p')"
else
  eval "$(systemctl --user show-environment 2>/dev/null \
          | sed -nE 's/^(DISPLAY|XAUTHORITY|WAYLAND_DISPLAY)=(.*)$/export \1="\2"/p')"
fi
: "${DISPLAY:=:1}"

ENVS=(HOME="$A" XDG_RUNTIME_DIR="$RT" DBUS_SESSION_BUS_ADDRESS="unix:path=$RT/bus"
      DISPLAY="$DISPLAY" steam_master_ipc_name_override="127.0.0.1:$PORT")
[ -n "${XAUTHORITY:-}" ] && ENVS+=(XAUTHORITY="$XAUTHORITY")
[ -n "${WAYLAND_DISPLAY:-}" ] && ENVS+=(WAYLAND_DISPLAY="$WAYLAND_DISPLAY")

as_user() {
  if [ "$(id -u)" = 0 ]; then runuser -u "$U" -- env "${ENVS[@]}" "$@";
  else env "${ENVS[@]}" "$@"; fi
}

# Поднять клиент, если его ещё нет
if ! pgrep -f "$A/.local/share/Steam/steamrt64/steam" >/dev/null; then
  rm -f "$A/.steam/steam.pid"
  if [ "$(id -u)" = 0 ]; then
    setsid runuser -u "$U" -- env "${ENVS[@]}" /usr/bin/steam \
      -master_ipc_name_override "127.0.0.1:$PORT" >/dev/null 2>&1 </dev/null &
  else
    setsid env "${ENVS[@]}" /usr/bin/steam \
      -master_ipc_name_override "127.0.0.1:$PORT" >/dev/null 2>&1 </dev/null &
  fi
  sleep 25
fi

# Запустить игру
as_user /usr/bin/steam -master_ipc_name_override "127.0.0.1:$PORT" -applaunch "$APPID"

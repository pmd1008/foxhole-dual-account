#!/bin/bash
# Foxhole — основной Steam-аккаунт (клиент на порту по умолчанию 57343).
#
# Переопределения:
#   FOXHOLE_USER   — пользователь сессии (по умолчанию владелец $HOME)
#   FOXHOLE_APPID  — AppID игры (по умолчанию 505460)
set -u

APPID="${FOXHOLE_APPID:-505460}"
if [ -z "${FOXHOLE_USER:-}" ]; then
  if [ "$(id -u)" = 0 ]; then U=pmd; else U=$(id -un); fi
else U="$FOXHOLE_USER"; fi
USER_HOME=$(getent passwd "$U" | cut -d: -f6)
MAIN="${FOXHOLE_MAIN_HOME:-$USER_HOME}"
RT="${XDG_RUNTIME_DIR:-/run/user/$(id -u "$U")}"

if [ "$(id -u)" = 0 ]; then
  eval "$(runuser -u "$U" -- env XDG_RUNTIME_DIR="$RT" systemctl --user show-environment 2>/dev/null \
          | sed -nE 's/^(DISPLAY|XAUTHORITY|WAYLAND_DISPLAY)=(.*)$/export \1="\2"/p')"
else
  eval "$(systemctl --user show-environment 2>/dev/null \
          | sed -nE 's/^(DISPLAY|XAUTHORITY|WAYLAND_DISPLAY)=(.*)$/export \1="\2"/p')"
fi
: "${DISPLAY:=:1}"

ENVS=(HOME="$MAIN" XDG_RUNTIME_DIR="$RT" DBUS_SESSION_BUS_ADDRESS="unix:path=$RT/bus" DISPLAY="$DISPLAY")
[ -n "${XAUTHORITY:-}" ] && ENVS+=(XAUTHORITY="$XAUTHORITY")
[ -n "${WAYLAND_DISPLAY:-}" ] && ENVS+=(WAYLAND_DISPLAY="$WAYLAND_DISPLAY")

as_user() {
  if [ "$(id -u)" = 0 ]; then runuser -u "$U" -- env "${ENVS[@]}" "$@";
  else env "${ENVS[@]}" "$@"; fi
}

if ! pgrep -f "$MAIN/.local/share/Steam/steamrt64/steam" >/dev/null; then
  if [ "$(id -u)" = 0 ]; then
    setsid runuser -u "$U" -- env "${ENVS[@]}" /usr/bin/steam >/dev/null 2>&1 </dev/null &
  else
    setsid env "${ENVS[@]}" /usr/bin/steam >/dev/null 2>&1 </dev/null &
  fi
  sleep 25
fi

as_user /usr/bin/steam -applaunch "$APPID"

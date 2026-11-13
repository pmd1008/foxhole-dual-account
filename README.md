# Foxhole: playing two characters at once

Runs two Foxhole windows from different Steam accounts on one screen. Each window has its
own keyboard and mouse, and input in one doesn't get in the way of the other.

Russian version: [README.ru.md](README.ru.md).

## Status

Raw prototype. Tested on one machine: Fedora 44, Plasma 6.7 X11, Foxhole under Proton,
two USB keyboards and two mice. No tests, haven't tried other distros (it's the same thing
there: X11 and uinput, differences are in the small details).

Nope.
Windows: too lazy to make it, and I don't like it. There it's either two VMs with USB
passthrough, or paid multiseat.

## Not a cheat

No game vulnerabilities, no code injection, no reading or patching process memory, no
network tricks, no anti-cheat bypass. Everything with normal tools:

- two Steam clients with their own settings (own HOME, own IPC port) — standard flags;
- the second keyboard and mouse are XInput2 in X11, which exists exactly for this;
- the autoclicker is a virtual `/dev/uinput` device, a normal mouse button press.

## Requirements

- Linux with Xorg (tested: Fedora 44, KDE Plasma 6.7, X11, NVIDIA RTX 5060 Ti).
- Two keyboards and two mice. A side button on the second mouse is optional.
- Steam + Proton.
- `xinput`, Python 3.11+, `python3-evdev`, write access to `/dev/uinput`.

Input permissions (without root in the session):

```bash
sudo tee /etc/udev/rules.d/60-foxhole-input.rules >/dev/null <<'EOF'
KERNEL=="uinput", TAG+="uaccess"
SUBSYSTEM=="input", TAG+="uaccess"
EOF
sudo udevadm control --reload && sudo udevadm trigger
```

## Install

```bash
git clone <repo> foxhole-dual && cd foxhole-dual
./install.sh --with-mpx      # launchers, shortcuts, foxhole-input, MPX daemons
./install.sh --shim          # optional: shim for the second client
```

## Usage

```bash
foxhole-input doctor     # check uinput / evdev / XInput2
foxhole-both             # start both clients and both games
```

Windows side by side, windowed/borderless — fullscreen might even work. The first pair
works in the first window, the second in the second.

The second seat is brought up by `seat2-start` on login. Its devices live in
`~/.config/foxhole-dual/devices.conf`:

```bash
foxhole-input devices        # list keyboards/mice and their seats
foxhole-input setup          # pick a pair for the second seat
foxhole-input setup --auto   # take whatever is on the second seat now
```

## Autoclicker

```bash
foxhole-input run      # daemon (can go to autostart)
foxhole-input status
foxhole-input stop
```

Config: `~/.config/foxhole-dual/input.toml`.

```toml
[[bind]]
trigger = "mouse:side"   # side button of any mouse, clicks at that mouse's cursor
action  = "click:0.05"
seat    = "auto"

[[bind]]
trigger = "key:j"        # J on this keyboard, seat taken from the keyboard
action  = "click:0.05"
seat    = "auto"

[[bind]]
trigger = "key:4"        # hold right mouse button for the twink
action  = "hold:right"
seat    = 2              # only from the second keyboard
```

`seat = auto` — the seat of the device that was pressed. `seat = 1/2` — fixed, and without
`device =` the binding only fires from devices of that seat. `click:N` — toggle, one click
every N seconds; `hold:left/right` — hold until pressed again. Triggers:
`key:x`, `ctrl+alt+a`, `mouse:side`, `mouse:extra`, `mouse:back`.

Don't run the old `autoclick`/`autoclick-hotkey`/`seat2-rmb-hold` at the same time as
`foxhole-input` — you'll get two triggers per press.

## Use cases

Mostly it's handy for driving a tank — if you have no friends or want to be much more
effective — put one character on the driver, the other on the gunner. That way you get a
good view and can pick off infantry in trenches at maximum range perfectly.

**Repairing.** Repair for the whole crew is available through the autoclicker:

1. get out;
2. press 1 to take the hammer;
3. aim at the tank;
4. press the autoclicker;
5. repeat with the other account — that way you repair at full power.

**Building.** Similarly you can build: first mark the blueprints, then switch each account
with the autoclicker — building together is faster.

**Spotter.** There's also the option of using the twink as a spotter when you fire from a
gunboat / hand mortar / anything else — I added an automatic right mouse button hold so the
spotter keeps the camera in one place and it's convenient for you to aim.

There are a mass of applications — the main thing is to have well-developed brain
hemispheres.

## How it works, briefly

- **Accounts:** the second client gets `-master_ipc_name_override 127.0.0.1:57344` and the
  same `steam_master_ipc_name_override` in the environment, which the game inherits.
  Without it both games grab the first client and show the same account.
- **Input:** XInput2 master pair `second pointer`/`second keyboard`. `seat2-cp` sets the
  window's ClientPointer by the game process `HOME`, `seat2-focuspin` keeps the second
  keyboard's XI focus on the Wine window (looks it up by `WM_STATE`, not by the KWin frame).
- **Clicks:** a `uinput` device is created and attached to the master of the seat that was
  pressed, so it clicks at that seat's cursor.

## Repo

```
install.sh              installer
scripts/foxhole-*.sh    account launchers (main / alt / both)
scripts/foxhole-input   autoclicker and bindings
config/input.toml       default bindings
config/devices.conf     which devices are on the second seat
mpx/                    XInput2: master pair, ClientPointer, focus, layout, tools
shim/homealt.c          optional LD_PRELOAD shim
desktop/                menu shortcuts
```

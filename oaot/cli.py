"""omarchy-always-on-top — keep a window above the others, and know which one.

    omarchy-always-on-top            pin or unpin the focused window
    omarchy-always-on-top list       which windows are pinned
    omarchy-always-on-top off        let them all go
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from . import __version__, menu
from .hypr import Hyprland, Window, plan_pin, plan_unpin

CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                          "omarchy-always-on-top")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
STATE_DIR = os.path.join(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")),
                         "omarchy-always-on-top")
STATE_FILE = os.path.join(STATE_DIR, "pinned.json")

ICONS = {"pin": "", "unpin": "", "window": "", "off": ""}
DEFAULTS = {"border": 3, "colour": "", "notify": True}


# ---------------------------------------------------------------- settings and state

def config() -> dict:
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return {**DEFAULTS, **json.load(f)}
    except (OSError, ValueError):
        return dict(DEFAULTS)


def theme_colour() -> str:
    """The accent colour of whatever theme is on, so the highlight belongs to it."""
    try:
        r = subprocess.run(["omarchy-theme-color", "accent"], capture_output=True,
                           timeout=10, check=False)
        value = r.stdout.decode("utf-8", "replace").strip()
    except (OSError, subprocess.SubprocessError):
        value = ""
    if value.startswith("#") and len(value) == 7:
        return f"rgb({value[1:]})"
    return "rgb(ff5555)"


def highlight_colour() -> str:
    chosen = config().get("colour") or ""
    if chosen.startswith("#") and len(chosen) == 7:
        return f"rgb({chosen[1:]})"
    return chosen or theme_colour()


def load_state() -> dict[str, dict]:
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if isinstance(v, dict)}
    except (OSError, ValueError, AttributeError):
        return {}


def save_state(state: dict[str, dict]) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp, STATE_FILE)


def prune(state: dict[str, dict], windows: list[Window]) -> dict[str, dict]:
    """Forget windows that have closed, and ones somebody else unpinned."""
    alive = {w.address: w for w in windows}
    return {address: entry for address, entry in state.items()
            if address in alive and alive[address].pinned}


# ---------------------------------------------------------------- commands

def cmd_toggle(args) -> int:
    hypr = Hyprland()
    window = hypr.active()
    if window is None:
        say("No window has the focus.")
        return 1
    settings = config()
    state = prune(load_state(), hypr.clients())

    if window.pinned:
        entry = state.pop(window.address, {})
        problems = hypr.apply(plan_unpin(window, bool(entry.get("floated"))))
        save_state(state)
        report(f"{window.label} is no longer on top", problems, settings)
        return 1 if problems else 0

    commands, floated = plan_pin(window, highlight_colour(), int(settings["border"]))
    problems = hypr.apply(commands)
    state[window.address] = {"class": window.klass, "title": window.title,
                             "floated": floated}
    save_state(state)
    report(f"{window.label} is on top", problems, settings)
    return 1 if problems else 0


def cmd_list(args) -> int:
    hypr = Hyprland()
    windows = hypr.clients()
    pinned = [w for w in windows if w.pinned]
    save_state(prune(load_state(), windows))
    if not pinned:
        print("Nothing is on top.")
        return 1
    for w in pinned:
        print(f"{w.address}  {w.label}")
    return 0


def cmd_off(args) -> int:
    hypr = Hyprland()
    windows = hypr.clients()
    state = load_state()
    pinned = [w for w in windows if w.pinned]
    if not pinned:
        print("Nothing is on top.")
        return 0
    problems = []
    for window in pinned:
        entry = state.pop(window.address, {})
        problems += hypr.apply(plan_unpin(window, bool(entry.get("floated"))))
    save_state(prune(state, hypr.clients()))
    report(f"{len(pinned)} window(s) let go", problems, config())
    return 1 if problems else 0


def cmd_status(args) -> int:
    hypr = Hyprland()
    settings = config()
    print(f"hyprctl        {'found' if hypr.available else 'NOT FOUND'}")
    print(f"highlight      {highlight_colour()}, {settings['border']}px "
          f"{'(from the theme)' if not settings.get('colour') else '(from your config)'}")
    windows = hypr.clients()
    pinned = [w for w in windows if w.pinned]
    print(f"on top         {len(pinned)}")
    for w in pinned:
        print(f"               {w.label}")
    remembered = prune(load_state(), windows)
    floated = [a for a, e in remembered.items() if e.get("floated")]
    print(f"floated by us  {len(floated)}")
    return 0


def cmd_menu(args) -> int:
    hypr = Hyprland()
    windows = hypr.clients()
    active = hypr.active()
    rows = []
    if active is not None:
        rows.append((ICONS["unpin"] if active.pinned else ICONS["pin"],
                     ("Let go of this window" if active.pinned else "Keep this window on top"),
                     active.label))
    for w in windows:
        if w.pinned and (active is None or w.address != active.address):
            rows.append((ICONS["window"], w.label, "on top · pick to let it go"))
    if any(w.pinned for w in windows):
        rows.append((ICONS["off"], "Let go of everything", "Unpin every window"))
    if not rows:
        say("No window has the focus.")
        return 1

    pick = menu.select("Always on top", rows, width=640)
    if not pick:
        return 1
    label = pick.split("\t")[0]
    if label == "Let go of everything":
        return cmd_off(args)
    if label in ("Keep this window on top", "Let go of this window"):
        return cmd_toggle(args)
    target = next((w for w in windows if w.pinned and w.label == label), None)
    if target is None:
        return 1
    state = load_state()
    entry = state.pop(target.address, {})
    problems = Hyprland().apply(plan_unpin(target, bool(entry.get("floated"))))
    save_state(state)
    report(f"{target.label} is no longer on top", problems, config())
    return 1 if problems else 0


# ---------------------------------------------------------------- output

def say(text: str) -> None:
    print(text)
    menu.notify("Always on top", text)


def report(text: str, problems: list[str], settings: dict) -> None:
    if problems:
        for problem in problems:
            print(f"omarchy-always-on-top: {problem}", file=sys.stderr)
        menu.notify("Always on top", problems[0])
        return
    print(text)
    if settings.get("notify", True):
        menu.notify("Always on top", text)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="omarchy-always-on-top",
        description="Keep a window above the others, and know which one.",
        epilog="With no command it pins or unpins the focused window.")
    p.add_argument("command", nargs="?", help="toggle, list, off, status, menu")
    p.add_argument("-V", "--version", action="version",
                   version=f"omarchy-always-on-top {__version__}")
    args = p.parse_args(argv)

    if not Hyprland().available:
        print("omarchy-always-on-top: hyprctl was not found — this needs Hyprland",
              file=sys.stderr)
        return 2

    commands = {"toggle": cmd_toggle, "list": cmd_list, "off": cmd_off,
                "status": cmd_status, "menu": cmd_menu}
    if args.command is None:
        return cmd_toggle(args)
    if args.command not in commands:
        print(f"omarchy-always-on-top: unknown command {args.command!r}", file=sys.stderr)
        return 2
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())

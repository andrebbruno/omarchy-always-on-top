"""Talking to Hyprland, and deciding what to say.

The decisions are pure functions that return a list of commands; something else runs
them. That separation is the point: pinning a window is a four-step dance whose order
matters, and the tests can check the dance without a compositor.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field

# Hyprland 0.56 names window properties in snake_case, and rejects anything else with
# a bare "Invalid prop name": it is activeBorderColor nowhere and active_border_color
# here. The dispatchers moved to Lua in the same release.
PROP_BORDER_COLOUR = "active_border_color"
PROP_BORDER_SIZE = "border_size"


@dataclass
class Window:
    address: str
    klass: str = ""
    title: str = ""
    floating: bool = False
    pinned: bool = False
    workspace: str = ""

    @classmethod
    def from_json(cls, data: dict) -> "Window":
        return cls(address=data.get("address", ""),
                   klass=data.get("class", "") or data.get("initialClass", ""),
                   title=data.get("title", ""),
                   floating=bool(data.get("floating")),
                   pinned=bool(data.get("pinned")),
                   workspace=str((data.get("workspace") or {}).get("name", "")))

    @property
    def label(self) -> str:
        return f"{self.klass or '?'} · {self.title}" if self.title else (self.klass or "?")


@dataclass
class Command:
    """Either a dispatch (Lua) or a window property change."""
    kind: str                      # "dispatch" | "prop"
    argument: str
    prop: str = ""
    value: str = ""

    def __repr__(self) -> str:     # readable test failures
        return (f"prop({self.argument}, {self.prop}={self.value})" if self.kind == "prop"
                else f"dispatch({self.argument})")


def dispatch(lua: str) -> Command:
    return Command("dispatch", lua)


def prop(address: str, name: str, value) -> Command:
    return Command("prop", address, name, str(value))


# ---------------------------------------------------------------- the decisions

def plan_pin(window: Window, colour: str, border: int) -> tuple[list[Command], bool]:
    """Commands to put this window on top, and whether we had to float it.

    Hyprland only pins floating windows — `pin` on a tiled one answers "Window does
    not qualify to be pinned" — so a tiled window is floated first, and remembering
    that is what lets unpinning give it back to the layout.
    """
    commands: list[Command] = []
    floated = False
    if not window.floating:
        commands.append(dispatch(f'hl.dsp.window.float({{ action = "toggle", '
                                 f'window = "address:{window.address}" }})'))
        floated = True
    if not window.pinned:
        commands.append(dispatch(f'hl.dsp.window.pin({{ window = "address:{window.address}" }})'))
    if border > 0:
        commands.append(prop(window.address, PROP_BORDER_COLOUR, colour))
        commands.append(prop(window.address, PROP_BORDER_SIZE, border))
    return commands, floated


def plan_unpin(window: Window, was_floated: bool) -> list[Command]:
    """Commands to let it go — including back into the layout if we took it out."""
    commands: list[Command] = []
    if window.pinned:
        commands.append(dispatch(f'hl.dsp.window.pin({{ window = "address:{window.address}" }})'))
    # "unset" puts a property back to whatever the config says, which is how the
    # window gets its theme border back rather than one we invented.
    commands.append(prop(window.address, PROP_BORDER_COLOUR, "unset"))
    commands.append(prop(window.address, PROP_BORDER_SIZE, "unset"))
    if was_floated and window.floating:
        commands.append(dispatch(f'hl.dsp.window.float({{ action = "toggle", '
                                 f'window = "address:{window.address}" }})'))
    return commands


# ---------------------------------------------------------------- running them

class Hyprland:
    """The thin layer that actually shells out to hyprctl."""

    def __init__(self, runner=None):
        self.runner = runner or self._run

    def _env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.setdefault("WAYLAND_DISPLAY", "wayland-1")
        if "HYPRLAND_INSTANCE_SIGNATURE" not in env:
            base = os.path.join(env.get("XDG_RUNTIME_DIR", "/run/user/1000"), "hypr")
            try:
                instances = sorted(os.listdir(base))
                if instances:
                    env["HYPRLAND_INSTANCE_SIGNATURE"] = instances[0]
            except OSError:
                pass
        return env

    def _run(self, args: list[str]) -> tuple[int, str]:
        try:
            r = subprocess.run(["hyprctl", *args], capture_output=True,
                               env=self._env(), timeout=10, check=False)
        except (OSError, subprocess.SubprocessError) as e:
            return 1, str(e)
        return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace").strip()

    @property
    def available(self) -> bool:
        return shutil.which("hyprctl") is not None

    def clients(self) -> list[Window]:
        code, out = self.runner(["clients", "-j"])
        if code != 0:
            return []
        try:
            return [Window.from_json(item) for item in json.loads(out)]
        except ValueError:
            return []

    def active(self) -> Window | None:
        code, out = self.runner(["activewindow", "-j"])
        if code != 0:
            return None
        try:
            data = json.loads(out)
        except ValueError:
            return None
        return Window.from_json(data) if data.get("address") else None

    def apply(self, commands: list[Command]) -> list[str]:
        """Run them in order; returns whatever went wrong, in the order it went wrong."""
        problems = []
        for command in commands:
            if command.kind == "dispatch":
                code, out = self.runner(["dispatch", command.argument])
            else:
                code, out = self.runner([
                    "dispatch",
                    f'hl.dsp.window.set_prop({{ window = "address:{command.argument}", '
                    f'prop = "{command.prop}", value = {_lua(command.value)} }})'])
            if code != 0 or out.lower().startswith(("error", "invalid")):
                problems.append(f"{command}: {out}")
        return problems


def _lua(value: str) -> str:
    """A Lua literal: numbers bare, everything else quoted."""
    text = str(value)
    if text.lstrip("-").isdigit():
        return text
    return '"' + text.replace('"', '\\"') + '"'

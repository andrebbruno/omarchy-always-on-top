# Always On Top for Omarchy

Keep a window above the others, and see at a glance which one. A port of
[PowerToys Always On Top](https://learn.microsoft.com/windows/powertoys/always-on-top) to
[Omarchy](https://omarchy.org).

*[Leia em português](README.pt-BR.md)*

```bash
omarchy-always-on-top          # pin or unpin the focused window
omarchy-always-on-top list     # which ones are up there
omarchy-always-on-top off      # let them all go
```

The pinned window gets a border in your theme's accent colour, so you can tell at a glance —
that is PowerToys' highlight, painted with Omarchy's palette.

## What it does that `hyprctl dispatch pin` does not

- **It works on a tiled window.** Hyprland only pins floating windows, and answers a tiled
  one with "Window does not qualify to be pinned". This floats it first.
- **It gives the window back.** Unpinning puts a window we floated back into the layout, and
  leaves one that was already floating exactly where it was. That is the whole reason there
  is a state file.
- **It marks the window**, with `active_border_color` and `border_size`, and clears both back
  to the theme's own values when you unpin.
- **It keeps up with you.** A window you closed, or unpinned some other way, is forgotten the
  next time the tool runs — Hyprland reuses addresses, and a stale entry would eventually
  point at somebody else's window.

## Install

### Arch / Omarchy

```bash
sudo pacman -U omarchy-always-on-top-*-any.pkg.tar.zst   # from Releases
```

The keybinding, in `~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + CTRL + T", "Always on top", "omarchy-always-on-top")
```

To change the highlight, `~/.config/omarchy-always-on-top/config.json`:

```json
{ "border": 3, "colour": "#ff8800", "notify": true }
```

`"colour"` takes a hex value or any Hyprland colour (`rgba(ff880080)`); leaving it empty
follows the theme's accent. `"border": 0` turns the highlight off.

### Elsewhere

`pipx install git+https://github.com/andrebbruno/omarchy-always-on-top`. Hyprland only — it
is `hyprctl` all the way down.

## Commands

```
omarchy-always-on-top            pin or unpin the focused window
omarchy-always-on-top menu       the Omarchy menu, including the other pinned windows
omarchy-always-on-top list       addresses and names
omarchy-always-on-top off        unpin everything
omarchy-always-on-top status     the highlight, what is pinned, what we floated
```

## Notes

- **A pinned window follows you between workspaces.** That is what pinning means in
  Hyprland, and it is usually the point.
- **Hyprland 0.56 renamed its window properties to snake_case** (`active_border_color`, not
  `activeBorderColor`) and moved dispatchers to Lua. Both are handled here; older Hyprland
  versions are not supported.

## Development

```bash
python -m pytest tests -q     # 36 tests, no compositor needed
```

What to do about a window is a pure function returning a list of commands, and something
else runs them — so the tests can check the order of the four-step pin dance, that a tiled
window is floated first, that unpinning restores the border and the layout, and that an
error printed on stdout (which `hyprctl` does while exiting 0) still counts as a failure.

## License

MIT © Andre Bruno

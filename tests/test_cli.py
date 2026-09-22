import json

import pytest

from oaot import cli
from oaot.hypr import Window

ADDRESS = "0xaaa"
OTHER = "0xbbb"


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "CONFIG_FILE", str(tmp_path / "config.json"))
    monkeypatch.setattr(cli, "STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(cli, "STATE_FILE", str(tmp_path / "state" / "pinned.json"))
    monkeypatch.setattr(cli.menu, "notify", lambda *a, **k: None)
    monkeypatch.setattr(cli, "theme_colour", lambda: "rgb(7aa2f7)")
    return tmp_path


class FakeHyprland:
    def __init__(self, windows, active=None):
        self.windows = windows
        self._active = active if active is not None else (windows[0] if windows else None)
        self.applied = []
        self.available = True

    def clients(self):
        return self.windows

    def active(self):
        return self._active

    def apply(self, commands):
        self.applied.extend(commands)
        return []


def use(monkeypatch, hypr):
    monkeypatch.setattr(cli, "Hyprland", lambda *a, **k: hypr)
    return hypr


def window(address=ADDRESS, **kwargs):
    base = dict(klass="foot", title="a terminal", floating=False, pinned=False)
    base.update(kwargs)
    return Window(address=address, **base)


# ---------------------------------------------------------------- toggling

def test_pinning_records_that_we_floated_it(home, monkeypatch):
    hypr = use(monkeypatch, FakeHyprland([window()]))
    assert cli.main(["toggle"]) == 0
    state = cli.load_state()
    assert state[ADDRESS]["floated"] is True
    assert state[ADDRESS]["class"] == "foot"


def test_pinning_a_window_that_was_already_floating(home, monkeypatch):
    use(monkeypatch, FakeHyprland([window(floating=True)]))
    cli.main(["toggle"])
    assert cli.load_state()[ADDRESS]["floated"] is False


def test_unpinning_forgets_it(home, monkeypatch):
    pinned = window(floating=True, pinned=True)
    use(monkeypatch, FakeHyprland([pinned]))
    cli.save_state({ADDRESS: {"floated": True, "class": "foot"}})
    assert cli.main(["toggle"]) == 0
    assert cli.load_state() == {}


def test_unpinning_puts_a_window_we_floated_back(home, monkeypatch):
    pinned = window(floating=True, pinned=True)
    hypr = use(monkeypatch, FakeHyprland([pinned]))
    cli.save_state({ADDRESS: {"floated": True}})
    cli.main(["toggle"])
    assert any("float" in c.argument for c in hypr.applied)


def test_unpinning_leaves_a_window_we_did_not_float_alone(home, monkeypatch):
    pinned = window(floating=True, pinned=True)
    hypr = use(monkeypatch, FakeHyprland([pinned]))
    cli.save_state({ADDRESS: {"floated": False}})
    cli.main(["toggle"])
    assert not any("float" in c.argument for c in hypr.applied)


def test_with_no_focused_window(home, monkeypatch, capsys):
    use(monkeypatch, FakeHyprland([], active=None))
    assert cli.main(["toggle"]) == 1
    assert "focus" in capsys.readouterr().out


# ---------------------------------------------------------------- state hygiene

def test_a_window_that_closed_is_forgotten(home, monkeypatch):
    """Addresses are reused by Hyprland, so stale entries are worse than useless."""
    hypr = use(monkeypatch, FakeHyprland([window(pinned=True)]))
    cli.save_state({ADDRESS: {"floated": True}, "0xdead": {"floated": True}})
    cli.main(["list"])
    assert list(cli.load_state()) == [ADDRESS]


def test_a_window_unpinned_by_someone_else_is_forgotten(home, monkeypatch):
    use(monkeypatch, FakeHyprland([window(pinned=False)]))
    cli.save_state({ADDRESS: {"floated": True}})
    cli.main(["list"])
    assert cli.load_state() == {}


def test_a_corrupt_state_file_is_not_an_error(home):
    (home / "state").mkdir()
    (home / "state" / "pinned.json").write_text("{not json", encoding="utf-8")
    assert cli.load_state() == {}


# ---------------------------------------------------------------- listing and off

def test_list_shows_the_pinned_windows(home, monkeypatch, capsys):
    use(monkeypatch, FakeHyprland([window(pinned=True), window(OTHER, pinned=False)]))
    assert cli.main(["list"]) == 0
    out = capsys.readouterr().out
    assert ADDRESS in out and OTHER not in out


def test_list_with_nothing_pinned(home, monkeypatch, capsys):
    use(monkeypatch, FakeHyprland([window()]))
    assert cli.main(["list"]) == 1
    assert "Nothing is on top" in capsys.readouterr().out


def test_off_unpins_every_one(home, monkeypatch):
    windows = [window(pinned=True, floating=True), window(OTHER, pinned=True, floating=True)]
    hypr = use(monkeypatch, FakeHyprland(windows))
    cli.save_state({ADDRESS: {"floated": True}, OTHER: {"floated": False}})
    assert cli.main(["off"]) == 0
    pins = [c for c in hypr.applied if "pin(" in c.argument]
    assert len(pins) == 2
    assert cli.load_state() == {}


def test_off_with_nothing_pinned(home, monkeypatch, capsys):
    use(monkeypatch, FakeHyprland([window()]))
    assert cli.main(["off"]) == 0


# ---------------------------------------------------------------- the highlight

def test_the_highlight_colour_comes_from_the_theme(home):
    assert cli.highlight_colour() == "rgb(7aa2f7)"


def test_a_configured_colour_wins(home):
    (home / "config.json").write_text(json.dumps({"colour": "#ff8800"}), encoding="utf-8")
    assert cli.highlight_colour() == "rgb(ff8800)"


def test_a_configured_rgb_colour_is_passed_through(home):
    (home / "config.json").write_text(json.dumps({"colour": "rgba(ff880080)"}),
                                      encoding="utf-8")
    assert cli.highlight_colour() == "rgba(ff880080)"


def test_the_border_width_can_be_configured(home, monkeypatch):
    (home / "config.json").write_text(json.dumps({"border": 6}), encoding="utf-8")
    hypr = use(monkeypatch, FakeHyprland([window()]))
    cli.main(["toggle"])
    sizes = [c.value for c in hypr.applied if c.kind == "prop" and c.prop.endswith("size")]
    assert sizes == ["6"]


def test_status_runs(home, monkeypatch, capsys):
    use(monkeypatch, FakeHyprland([window(pinned=True)]))
    assert cli.main(["status"]) == 0
    assert "on top" in capsys.readouterr().out


def test_an_unknown_command(home, monkeypatch, capsys):
    use(monkeypatch, FakeHyprland([window()]))
    assert cli.main(["frobnicate"]) == 2

import json

from oaot.hypr import (PROP_BORDER_COLOUR, PROP_BORDER_SIZE, Hyprland, Window,
                       plan_pin, plan_unpin)

ADDRESS = "0x5e1eda9ef460"


def window(**kwargs):
    return Window(address=ADDRESS, klass="foot", title="a terminal", **kwargs)


def kinds(commands):
    return [c.kind for c in commands]


# ---------------------------------------------------------------- pinning

def test_a_tiled_window_is_floated_before_it_is_pinned():
    """Hyprland answers "Window does not qualify to be pinned" otherwise."""
    commands, floated = plan_pin(window(floating=False), "rgb(ff5555)", 3)
    assert floated is True
    assert "float" in commands[0].argument
    assert "pin" in commands[1].argument
    assert commands.index([c for c in commands if "float" in c.argument][0]) < \
        commands.index([c for c in commands if "pin(" in c.argument][0])


def test_a_floating_window_is_pinned_where_it_is():
    commands, floated = plan_pin(window(floating=True), "rgb(ff5555)", 3)
    assert floated is False
    assert not any("float" in c.argument for c in commands)
    assert any("pin(" in c.argument for c in commands)


def test_a_window_that_is_already_pinned_is_not_pinned_again():
    commands, _ = plan_pin(window(floating=True, pinned=True), "rgb(ff5555)", 3)
    assert not any("pin(" in c.argument for c in commands)


def test_the_highlight_is_applied():
    commands, _ = plan_pin(window(floating=True), "rgb(00ff00)", 4)
    props = {c.prop: c.value for c in commands if c.kind == "prop"}
    assert props[PROP_BORDER_COLOUR] == "rgb(00ff00)"
    assert props[PROP_BORDER_SIZE] == "4"


def test_a_border_of_zero_means_no_highlight():
    commands, _ = plan_pin(window(floating=True), "rgb(00ff00)", 0)
    assert kinds(commands) == ["dispatch"]


def test_the_address_is_carried_in_every_command():
    commands, _ = plan_pin(window(), "rgb(ff5555)", 3)
    for command in commands:
        assert ADDRESS in (command.argument if command.kind == "dispatch" else command.argument)


# ---------------------------------------------------------------- unpinning

def test_unpinning_clears_the_highlight_back_to_the_theme():
    commands = plan_unpin(window(floating=True, pinned=True), was_floated=False)
    props = {c.prop: c.value for c in commands if c.kind == "prop"}
    assert props[PROP_BORDER_COLOUR] == "unset"
    assert props[PROP_BORDER_SIZE] == "unset"


def test_a_window_we_floated_goes_back_into_the_layout():
    commands = plan_unpin(window(floating=True, pinned=True), was_floated=True)
    assert "float" in commands[-1].argument


def test_a_window_that_was_already_floating_is_left_floating():
    commands = plan_unpin(window(floating=True, pinned=True), was_floated=False)
    assert not any("float" in c.argument for c in commands)


def test_unpinning_something_already_unpinned_still_clears_the_border():
    commands = plan_unpin(window(floating=True, pinned=False), was_floated=False)
    assert not any("pin(" in c.argument for c in commands)
    assert len([c for c in commands if c.kind == "prop"]) == 2


def test_unpin_comes_before_the_window_is_tiled_again():
    commands = plan_unpin(window(floating=True, pinned=True), was_floated=True)
    order = [c.argument for c in commands if c.kind == "dispatch"]
    assert "pin(" in order[0] and "float" in order[1]


# ---------------------------------------------------------------- the thin layer

class FakeHyprctl:
    def __init__(self, clients=(), active=None, fail_on=""):
        self.calls: list[list[str]] = []
        self._clients = list(clients)
        self._active = active
        self.fail_on = fail_on

    def __call__(self, args):
        self.calls.append(args)
        if args[:2] == ["clients", "-j"]:
            return 0, json.dumps(self._clients)
        if args[:2] == ["activewindow", "-j"]:
            return 0, json.dumps(self._active or {})
        if self.fail_on and self.fail_on in " ".join(args):
            return 1, "error: =[C]:-1: Invalid prop name"
        return 0, "ok"


def client(**kwargs):
    base = {"address": ADDRESS, "class": "foot", "title": "a terminal",
            "floating": False, "pinned": False, "workspace": {"name": "1"}}
    base.update(kwargs)
    return base


def test_clients_are_parsed():
    hypr = Hyprland(FakeHyprctl(clients=[client(pinned=True)]))
    windows = hypr.clients()
    assert len(windows) == 1
    assert windows[0].klass == "foot" and windows[0].pinned is True


def test_an_empty_active_window_is_none():
    assert Hyprland(FakeHyprctl(active={})).active() is None


def test_broken_json_is_not_a_crash():
    class Broken:
        def __call__(self, args):
            return 0, "{not json"
    assert Hyprland(Broken()).clients() == []
    assert Hyprland(Broken()).active() is None


def test_properties_are_sent_as_lua_with_the_right_quoting():
    fake = FakeHyprctl()
    commands, _ = plan_pin(window(floating=True), "rgb(ff5555)", 3)
    Hyprland(fake).apply(commands)
    sent = " ".join(" ".join(c) for c in fake.calls)
    assert 'prop = "active_border_color", value = "rgb(ff5555)"' in sent
    assert 'prop = "border_size", value = 3' in sent          # a number, unquoted


def test_a_refused_property_is_reported():
    fake = FakeHyprctl(fail_on="border_size")
    commands, _ = plan_pin(window(floating=True), "rgb(ff5555)", 3)
    problems = Hyprland(fake).apply(commands)
    assert len(problems) == 1
    assert "border_size" in problems[0]


def test_an_error_printed_on_stdout_still_counts_as_a_problem():
    """hyprctl exits 0 and prints "error: ..." — taking that as success hides failures."""
    class PrintsError:
        def __call__(self, args):
            return 0, "error: =[C]:-1: Window does not qualify to be pinned"
    commands, _ = plan_pin(window(), "rgb(ff5555)", 0)
    assert Hyprland(PrintsError()).apply(commands)

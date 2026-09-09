"""Checkbox TUI for `skillize.yaml`. Textual is the renderer; policy stays ours."""

from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Label, SelectionList, Static, TextArea
from textual.widgets.selection_list import Selection

from .catalogue import compose_skills
from .policy import Policy, Skill, load_policy_or_empty, save_policy


class WhenScreen(ModalScreen[str | None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("ctrl+s", "accept", "Save", show=True),
    ]

    CSS = """
    WhenScreen {
        align: center middle;
    }

    #when-dialog {
        width: 72;
        height: 18;
        background: $surface;
        border: round $accent;
        padding: 1 2;
    }

    #when-edit {
        height: 1fr;
        margin: 1 0;
    }
    """

    def __init__(self, name: str, when: str | None) -> None:
        super().__init__()
        self._name = name
        self._when = when or ""

    def compose(self) -> ComposeResult:
        with Vertical(id="when-dialog"):
            yield Label(f"When to use  {self._name}")
            yield TextArea(self._when, id="when-edit")
            yield Button("Save", id="ok", variant="primary")
            yield Button("Cancel", id="cancel")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_accept(self) -> None:
        text = self.query_one("#when-edit", TextArea).text.strip()
        self.dismiss(text)

    @on(Button.Pressed, "#ok")
    def on_ok(self) -> None:
        self.action_accept()

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.action_cancel()


class ConfigureApp(App[None]):
    TITLE = "skillize"
    CSS = """
    Screen {
        background: $background;
    }

    SelectionList {
        border: round $accent;
        height: 1fr;
        padding: 0 1;
    }

    #when {
        height: 8;
        border: round $panel;
        padding: 0 1;
        color: $text-muted;
    }

    #status {
        height: 1;
        color: $text-muted;
        padding: 0 1;
    }
    """
    BINDINGS = [
        Binding("s", "save", "Save"),
        Binding("e", "edit_when", "When"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, root: Path) -> None:
        super().__init__()
        self._root = root
        policy = load_policy_or_empty(root)
        skills = compose_skills(root, policy)
        self._path = policy.path
        self._when = {skill.name: skill.when for skill in skills}
        self._initial = _snapshot(skills)
        self._skills = skills
        self.sub_title = str(root)

    def compose(self) -> ComposeResult:
        yield Header()
        if not self._skills:
            yield Static(
                "No skills in .agents/skills or skillize.yaml.\n"
                "q quit",
                id="empty",
            )
        else:
            yield SelectionList[str](
                *[
                    Selection(skill.name, skill.name, skill.enabled)
                    for skill in self._skills
                ],
                id="skills",
            )
            yield Static(id="when")
            yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        if not self._skills:
            return
        listing = self.query_one("#skills", SelectionList)
        listing.border_title = "Skills"
        self._refresh_when()
        self._refresh_status()

    def _highlighted_name(self) -> str | None:
        listing = self.query_one("#skills", SelectionList)
        highlighted = listing.highlighted
        if highlighted is None:
            return None
        selection = listing.get_option_at_index(highlighted)
        return str(selection.value)

    def _current_skills(self) -> tuple[Skill, ...]:
        selected = set()
        if self._skills:
            selected = set(self.query_one("#skills", SelectionList).selected)
        return tuple(
            Skill(name=skill.name, enabled=skill.name in selected, when=self._when[skill.name])
            for skill in self._skills
        )

    def _refresh_when(self) -> None:
        name = self._highlighted_name()
        if name is None:
            return
        prose = self._when.get(name) or "No when text yet. Press e to add some."
        panel = self.query_one("#when", Static)
        panel.border_title = f"When · {name}"
        panel.update(prose)

    def _refresh_status(self) -> None:
        if not self._skills:
            return
        dirty = _snapshot(self._current_skills()) != self._initial
        mark = "unsaved" if dirty else "saved"
        on = sum(1 for skill in self._current_skills() if skill.enabled)
        self.query_one("#status", Static).update(
            f"{self._path.name}  ·  {on} on  ·  {mark}"
        )

    @on(SelectionList.SelectedChanged)
    @on(SelectionList.SelectionHighlighted)
    def on_list_changed(self) -> None:
        self._refresh_when()
        self._refresh_status()

    def action_edit_when(self) -> None:
        name = self._highlighted_name()
        if name is None:
            return

        def apply(result: str | None) -> None:
            if result is None:
                return
            self._when[name] = result or None
            self._refresh_when()
            self._refresh_status()

        self.push_screen(WhenScreen(name, self._when.get(name)), apply)

    def action_save(self) -> None:
        if not self._skills:
            return
        policy = Policy(path=self._path, version=1, skills=self._current_skills())
        save_policy(policy)
        self._initial = _snapshot(policy.skills)
        self._refresh_status()
        self.notify(f"Wrote {self._path.name}")


def _snapshot(skills: tuple[Skill, ...]) -> tuple[tuple[str, bool, str | None], ...]:
    return tuple((skill.name, skill.enabled, skill.when) for skill in skills)


def run_configure(root: Path) -> int:
    ConfigureApp(root).run()
    return 0

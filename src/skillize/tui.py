"""Browse GitHub packs, then checkbox TUI for `skillize.yaml`."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    SelectionList,
    Static,
    TextArea,
)
from textual.widgets.option_list import Option
from textual.widgets.selection_list import Selection

from .catalogue import compose_skills
from .errors import SkillizeError
from .install import install_skill
from .policy import Policy, Skill, load_policy_or_empty, save_policy
from .sources import (
    LOCAL_REPO,
    RemoteSkill,
    filter_entries,
    names_of,
    refresh_catalogue,
    skill_slug,
    split_catalogue,
)
from .store_tree import ensure_data_dir

InstallFn = Callable[..., Path]

CONFIGURE_CSS = """
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

CONFIGURE_BINDINGS = [
    Binding("s", "save", "Save"),
    Binding("e", "edit_when", "When"),
    Binding("q", "quit", "Quit"),
]


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


class ConfigureTools:
    """Enable/when UI shared by the standalone app (tests) and the pushed screen."""

    def configure_init(self, root: Path, policy: Policy, skills: tuple[Skill, ...]) -> None:
        self._root = root
        self._policy = policy
        self._keep = {skill.name for skill in policy.skills}
        self._path = policy.path
        self._when = {skill.name: skill.when for skill in skills}
        self._initial = _snapshot(skills)
        self._skills = skills

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
        current = self._current_skills()
        kept = tuple(
            skill
            for skill in current
            if skill.enabled or skill.when or skill.name in self._keep
        )
        policy = Policy(
            path=self._path,
            version=1,
            skills=kept,
            sources=self._policy.sources,
            sources_declared=self._policy.sources_declared,
        )
        save_policy(policy)
        self._keep = {skill.name for skill in kept}
        self._initial = _snapshot(current)
        self._refresh_status()
        self.notify(f"Wrote {self._path.name}")


class ConfigureApp(ConfigureTools, App[None]):
    TITLE = "skillize"
    CSS = CONFIGURE_CSS
    BINDINGS = CONFIGURE_BINDINGS

    def __init__(self, root: Path, policy: Policy, skills: tuple[Skill, ...]) -> None:
        super().__init__()
        self.configure_init(root, policy, skills)
        self.sub_title = str(root)


class ConfigureScreen(ConfigureTools, Screen[None]):
    CSS = CONFIGURE_CSS
    BINDINGS = [
        *CONFIGURE_BINDINGS,
        Binding("escape", "close_configure", "Back", show=True),
        Binding("b", "close_configure", "Back"),
    ]

    def __init__(self, root: Path, policy: Policy, skills: tuple[Skill, ...]) -> None:
        super().__init__()
        self.configure_init(root, policy, skills)

    def action_close_configure(self) -> None:
        self.dismiss()

    def action_quit(self) -> None:
        self.app.exit()


CATALOGUE_CSS = """
Screen {
    background: $background;
}

Input {
    margin: 0 1 1 1;
    border: round $accent;
}

OptionList {
    border: round $accent;
    height: 1fr;
    padding: 0 1;
}

#hint {
    height: 5;
    color: $text-muted;
    padding: 0 1;
    border: round $panel;
    margin: 0 1 1 1;
}
"""


class CatalogueTools:
    """Searchable list used by Installed (app) and Install (pushed screen)."""

    def catalogue_init(
        self,
        root: Path,
        policy: Policy,
        entries: tuple[RemoteSkill, ...],
        note: str,
        install: InstallFn,
        *,
        want_installed: bool,
    ) -> None:
        self._root = root
        self._policy = policy
        self._entries = tuple(sorted(entries, key=lambda entry: (entry.repo, entry.name)))
        self._note = note
        self._install = install
        self._want_installed = want_installed
        self._visible: tuple[RemoteSkill, ...] = ()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(placeholder=self._search_placeholder(), id="search")
        yield OptionList(id="browse")
        yield Static(id="hint")
        yield Footer()

    def on_mount(self) -> None:
        listing = self.query_one("#browse", OptionList)
        listing.border_title = "Installed" if self._want_installed else "Install New"
        self._refresh_list()
        self.query_one("#search", Input).focus()

    def on_screen_resume(self) -> None:
        self._policy = load_policy_or_empty(self._root)
        self._refresh_list()

    def _search_placeholder(self) -> str:
        if self._want_installed:
            return "Search installed skills…"
        return "Search packs to install…"

    def _pool(self) -> tuple[RemoteSkill, ...]:
        installed, available = split_catalogue(self._root, self._entries)
        return installed if self._want_installed else available

    def _query(self) -> str:
        return self.query_one("#search", Input).value

    def _refresh_list(self) -> None:
        listing = self.query_one("#browse", OptionList)
        self._visible = filter_entries(self._pool(), self._query())
        listing.clear_options()
        listing.add_options([Option(self._prompt(entry)) for entry in self._visible])
        if self._visible:
            listing.highlighted = 0
        self._refresh_hint()

    def _prompt(self, entry: RemoteSkill) -> str:
        if entry.repo == LOCAL_REPO:
            return entry.name
        return skill_slug(entry)

    def _highlighted_entry(self) -> RemoteSkill | None:
        listing = self.query_one("#browse", OptionList)
        index = listing.highlighted
        if index is None or index < 0 or index >= len(self._visible):
            return None
        return self._visible[index]

    def _refresh_hint(self) -> None:
        panel = self.query_one("#hint", Static)
        entry = self._highlighted_entry()
        if self._want_installed:
            keys = "c enable  ·  b home  ·  q quit"
        else:
            keys = "Enter / i install  ·  b home  ·  q quit"
        if entry is None:
            if self._pool() or self._query():
                panel.update(f"{self._root}\n{self._note}\nNo match. {keys}")
            elif self._want_installed:
                panel.update(
                    f"{self._root}\n{self._note}\n"
                    "Nothing on disk yet. b home, then Install New."
                )
            else:
                panel.update(
                    f"{self._root}\n{self._note or 'No GitHub packs listed.'}\n"
                    "Add sources: in skillize.yaml. b home, q quit."
                )
            return
        panel.update(f"{self._root}\n{entry.skill_path}  ·  {keys}")

    @on(Input.Changed, "#search")
    def on_search_changed(self) -> None:
        self._refresh_list()

    @on(Input.Submitted, "#search")
    def on_search_submitted(self) -> None:
        self.query_one("#browse", OptionList).focus()

    @on(OptionList.OptionHighlighted, "#browse")
    def on_browse_highlighted(self) -> None:
        self._refresh_hint()

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_blur_search(self) -> None:
        self.query_one("#browse", OptionList).focus()

    def action_configure(self) -> None:
        policy = load_policy_or_empty(self._root)
        extra = names_of(self._entries)
        skills = compose_skills(self._root, policy, extra_names=extra)
        self.push_screen(ConfigureScreen(self._root, policy, skills))


HOME_CSS = """
Screen {
    background: $background;
}

OptionList {
    border: round $accent;
    height: auto;
    max-height: 1fr;
    padding: 1 1;
    margin: 1 1;
}

#hint {
    height: 5;
    color: $text-muted;
    padding: 0 1;
    border: round $panel;
    margin: 0 1 1 1;
}
"""


class SkillizeApp(App[None]):
    TITLE = "skillize"
    CSS = HOME_CSS
    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        root: Path,
        policy: Policy,
        entries: tuple[RemoteSkill, ...],
        note: str = "",
        *,
        install: InstallFn = install_skill,
    ) -> None:
        super().__init__()
        self._root = root
        self._policy = policy
        self._entries = tuple(sorted(entries, key=lambda entry: (entry.repo, entry.name)))
        self._note = note
        self._install = install
        self.sub_title = f"{root} · {note}" if note else str(root)

    def compose(self) -> ComposeResult:
        yield Header()
        yield OptionList(id="menu")
        yield Static(id="hint")
        yield Footer()

    def on_mount(self) -> None:
        listing = self.query_one("#menu", OptionList)
        listing.border_title = "skillize"
        self._fill_menu()
        listing.focus()

    def on_screen_resume(self) -> None:
        self._policy = load_policy_or_empty(self._root)
        self._fill_menu()

    def _fill_menu(self) -> None:
        installed, available = split_catalogue(self._root, self._entries)
        listing = self.query_one("#menu", OptionList)
        listing.clear_options()
        listing.add_options(
            [
                Option(f"Installed ({len(installed)})", id="installed"),
                Option(f"Install New ({len(available)})", id="install"),
            ]
        )
        listing.highlighted = 0
        self.query_one("#hint", Static).update(
            f"{self._root}\n{self._note}\nEnter opens  ·  q quit"
        )

    def _open_choice(self, choice: str | None) -> None:
        if choice == "install":
            self.push_screen(
                InstallScreen(
                    self._root,
                    self._policy,
                    self._entries,
                    self._note,
                    install=self._install,
                )
            )
            return
        self.push_screen(
            InstalledScreen(
                self._root,
                self._policy,
                self._entries,
                self._note,
                install=self._install,
            )
        )

    @on(OptionList.OptionSelected, "#menu")
    def on_menu_selected(self, event: OptionList.OptionSelected) -> None:
        choice = event.option_id
        if choice not in ("installed", "install"):
            choice = "install" if event.option_index == 1 else "installed"
        self._open_choice(choice)


class InstalledScreen(CatalogueTools, Screen[None]):
    CSS = CATALOGUE_CSS
    BINDINGS = [
        Binding("slash", "focus_search", "Search"),
        Binding("c", "configure", "Enable"),
        Binding("escape", "close_list", "Home", show=True),
        Binding("b", "close_list", "Home"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        root: Path,
        policy: Policy,
        entries: tuple[RemoteSkill, ...],
        note: str = "",
        *,
        install: InstallFn = install_skill,
    ) -> None:
        super().__init__()
        self.catalogue_init(root, policy, entries, note, install, want_installed=True)

    def action_close_list(self) -> None:
        self.dismiss()

    def action_quit(self) -> None:
        self.app.exit()


class InstallScreen(CatalogueTools, Screen[None]):
    CSS = CATALOGUE_CSS
    BINDINGS = [
        Binding("slash", "focus_search", "Search"),
        Binding("i", "install", "Install"),
        Binding("escape", "close_install", "Home", show=True),
        Binding("b", "close_install", "Home"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        root: Path,
        policy: Policy,
        entries: tuple[RemoteSkill, ...],
        note: str = "",
        *,
        install: InstallFn = install_skill,
    ) -> None:
        super().__init__()
        self.catalogue_init(root, policy, entries, note, install, want_installed=False)

    def action_close_install(self) -> None:
        self.dismiss()

    def action_quit(self) -> None:
        self.app.exit()

    @on(OptionList.OptionSelected, "#browse")
    def on_browse_selected(self) -> None:
        self.action_install()

    def action_install(self) -> None:
        entry = self._highlighted_entry()
        if entry is None:
            return
        try:
            dest = self._install(self._root, entry)
        except SkillizeError as exc:
            self.notify(str(exc), severity="error")
            return
        self.notify(f"Installed {entry.name} → {dest}")
        self._refresh_list()


def _snapshot(skills: tuple[Skill, ...]) -> tuple[tuple[str, bool, str | None], ...]:
    return tuple((skill.name, skill.enabled, skill.when) for skill in skills)


def run_configure(root: Path) -> int:
    ensure_data_dir(root)
    policy = load_policy_or_empty(root)
    entries, note = refresh_catalogue(root, policy)
    print(f"skillize: {note}", file=sys.stderr)
    SkillizeApp(root, policy, entries, note).run()
    return 0

"""Browse GitHub packs, then checkbox TUI for `skillize.yaml`."""

from __future__ import annotations

import asyncio
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

from .errors import SkillizeError
from .install import install_skill
from .policy import (
    Policy,
    Skill,
    load_policy_or_empty,
    save_policy,
    with_skill_enabled,
    with_skill_when,
)
from .sources import (
    LOCAL_REPO,
    RemoteSkill,
    filter_entries,
    refresh_catalogue,
    skill_slug,
    split_catalogue,
)
from .store_tree import ensure_data_dir

InstallFn = Callable[..., Path]

# Ink cabinet + brass live fuse. Not cream/terracotta, not acid-green terminal.
INK = """
$background: #16141a;
$surface: #221f28;
$primary: #d4a574;
$secondary: #8a9e8f;
$accent: #d4a574;
$warning: #c45c4a;
$error: #c45c4a;
$success: #8a9e8f;
$text: #ece6d8;
$text-muted: #9a9284;
"""

CONFIGURE_CSS = (
    INK
    + """
Screen {
    background: $background;
    color: $text;
}

SelectionList {
    border: tall $accent;
    height: 1fr;
    padding: 0 1;
    margin: 0 1;
}

#when {
    height: 8;
    border: tall $surface;
    padding: 0 1;
    margin: 0 1 1 1;
    color: $text-muted;
}

#status {
    height: 1;
    color: $text-muted;
    padding: 0 1;
    margin: 0 1;
}
"""
)

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

    CSS = (
        INK
        + """
    WhenScreen {
        align: center middle;
    }

    #when-dialog {
        width: 72;
        height: 18;
        background: $surface;
        border: tall $accent;
        padding: 1 2;
    }

    #when-edit {
        height: 1fr;
        margin: 1 0;
    }
    """
    )

    def __init__(self, name: str, when: str | None) -> None:
        super().__init__()
        self._name = name
        self._when = when or ""

    def compose(self) -> ComposeResult:
        with Vertical(id="when-dialog"):
            yield Label(f"When to use {self._name}")
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
        listing.border_title = "On this tree"
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
        prose = self._when.get(name) or (
            "No when text yet. Press e to say when this skill should fire."
        )
        panel = self.query_one("#when", Static)
        panel.border_title = f"When for {name}"
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

    # Named by Textual convention, not @on: see CatalogueTools below.
    def on_selection_list_selected_changed(self) -> None:
        self._refresh_when()
        self._refresh_status()

    def on_selection_list_selection_highlighted(self) -> None:
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

        self.app.push_screen(WhenScreen(name, self._when.get(name)), apply)

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


CATALOGUE_CSS = (
    INK
    + """
Screen {
    background: $background;
    color: $text;
}

Input {
    margin: 0 1 1 1;
    border: tall $surface;
    background: $surface;
}

OptionList {
    border: tall $accent;
    height: 1fr;
    padding: 0 1;
    margin: 0 1;
}

#hint {
    height: 6;
    color: $text-muted;
    padding: 0 1;
    border: tall $surface;
    margin: 0 1 1 1;
}
"""
)


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
        listing.border_title = "On this tree" if self._want_installed else "From packs"
        self._refresh_list()
        listing.focus()

    def on_screen_resume(self) -> None:
        self._policy = load_policy_or_empty(self._root)
        self._refresh_list()

    def _search_placeholder(self) -> str:
        if self._want_installed:
            return "Filter installed skills"
        return "Filter packs"

    def _pool(self) -> tuple[RemoteSkill, ...]:
        installed, available = split_catalogue(self._root, self._entries)
        return installed if self._want_installed else available

    def _query(self) -> str:
        return self.query_one("#search", Input).value

    def _refresh_list(self, *, keep: str | None = None) -> None:
        listing = self.query_one("#browse", OptionList)
        current = self._highlighted_entry()
        retain = keep or (current.name if current is not None else None)
        self._visible = filter_entries(self._pool(), self._query())
        listing.clear_options()
        listing.add_options([Option(self._prompt(entry)) for entry in self._visible])
        index = 0
        if retain:
            for offset, entry in enumerate(self._visible):
                if entry.name == retain:
                    index = offset
                    break
        if self._visible:
            listing.highlighted = index
        self._refresh_hint()

    def _skill_is_on(self, name: str) -> bool:
        return any(skill.enabled and skill.name == name for skill in self._policy.skills)

    def _prompt(self, entry: RemoteSkill) -> str:
        slug = entry.name if entry.repo == LOCAL_REPO else skill_slug(entry)
        if not self._want_installed:
            return slug
        mark = "on " if self._skill_is_on(entry.name) else "off"
        return f"{mark}  {slug}"

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
            keys = "Space, Enter or c turns it on or off. e edits when. / search. b home."
        else:
            keys = "Enter or i copies it onto this tree. / search. b home."
        if entry is None:
            if self._pool() or self._query():
                panel.update(f"No match.\n{keys}")
            elif self._want_installed:
                panel.update(
                    "Nothing on disk yet.\nOpen From packs, install one, then come back."
                )
            else:
                panel.update(
                    f"{self._note or 'No packs listed.'}\n"
                    "Add sources: in skillize.yaml if the catalogue is empty."
                )
            return
        if self._want_installed:
            state = "on" if self._skill_is_on(entry.name) else "off"
            panel.update(f"{entry.name} is {state}.\n{keys}")
            return
        panel.update(f"{entry.skill_path}\n{keys}")

    # Named by Textual convention, not @on: a plain mixin is not a MessagePump
    # subclass, so decorated handlers declared here are never registered.
    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self._refresh_list()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search":
            self.query_one("#browse", OptionList).focus()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "browse":
            self._refresh_hint()

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_blur_search(self) -> None:
        self.query_one("#browse", OptionList).focus()


HOME_CSS = (
    INK
    + """
Screen {
    background: $background;
    color: $text;
}

OptionList {
    border: tall $accent;
    height: auto;
    max-height: 1fr;
    padding: 1 1;
    margin: 1 1;
}

#hint {
    height: 6;
    color: $text-muted;
    padding: 0 1;
    border: tall $surface;
    margin: 0 1 1 1;
}
"""
)


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

    def _reload_menu(self, _result: None = None) -> None:
        """Re-count from disk. ScreenResume does not bubble to the App."""
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
            "Installed is what is already on this tree. "
            "Install New copies a pack onto disk.\n"
            "Enter opens. q quits."
        )

    def _open_choice(self, choice: str | None) -> None:
        make = InstallScreen if choice == "install" else InstalledScreen
        screen = make(
            self._root,
            self._policy,
            self._entries,
            self._note,
            install=self._install,
        )
        self.push_screen(screen, self._reload_menu)

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
        Binding("space", "toggle_enabled", "On/off"),
        Binding("c", "toggle_enabled", "On/off"),
        Binding("e", "edit_when", "When"),
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

    @on(OptionList.OptionSelected, "#browse")
    def on_browse_selected(self) -> None:
        self.action_toggle_enabled()

    def action_toggle_enabled(self) -> None:
        entry = self._highlighted_entry()
        if entry is None:
            return
        turned_on = not self._skill_is_on(entry.name)
        self._policy = with_skill_enabled(self._policy, entry.name, turned_on)
        save_policy(self._policy)
        self._refresh_list(keep=entry.name)
        self.notify(f"{entry.name} {'on' if turned_on else 'off'}")

    def action_edit_when(self) -> None:
        entry = self._highlighted_entry()
        if entry is None:
            return
        current = next(
            (skill.when for skill in self._policy.skills if skill.name == entry.name),
            None,
        )

        def apply(result: str | None) -> None:
            if result is None:
                return
            self._policy = with_skill_when(self._policy, entry.name, result or None)
            save_policy(self._policy)
            self._refresh_hint()
            self.notify(f"When saved for {entry.name}")

        self.app.push_screen(WhenScreen(entry.name, current), apply)


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
        self._busy = False

    def action_close_install(self) -> None:
        if self._busy:
            return
        self.dismiss()

    def action_quit(self) -> None:
        self.app.exit()

    @on(OptionList.OptionSelected, "#browse")
    def on_browse_selected(self) -> None:
        self.action_install()

    def action_install(self) -> None:
        if self._busy:
            return
        entry = self._highlighted_entry()
        if entry is None:
            return
        self._busy = True
        listing = self.query_one("#browse", OptionList)
        search = self.query_one("#search", Input)
        listing.disabled = True
        search.disabled = True
        self.query_one("#hint", Static).update(
            f"Installing {self._prompt(entry)}…\n"
            "Fetching files. The list will update when it finishes."
        )
        self.run_worker(self._install_worker(entry), exclusive=True, group="install")

    async def _install_worker(self, entry: RemoteSkill) -> None:
        listing = self.query_one("#browse", OptionList)
        search = self.query_one("#search", Input)
        try:
            dest = await asyncio.to_thread(self._install, self._root, entry)
        except SkillizeError as exc:
            self.notify(str(exc), severity="error")
        else:
            self.notify(f"Installed {entry.name} → {dest}")
        finally:
            self._busy = False
            listing.disabled = False
            search.disabled = False
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

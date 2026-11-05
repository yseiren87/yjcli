"""Prompt widgets (checkbox, text, select) where ← goes back one screen.

`Prompter` is what the wizards talk to; `QuestionaryPrompter` is the terminal one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

import questionary
import questionary.prompts.common as qc
from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings

BACK = object()  # the user pressed ←

qc.INDICATOR_SELECTED = "[x]"
qc.INDICATOR_UNSELECTED = "[ ]"


@dataclass
class Item:
    value: str
    title: str
    checked: bool = False
    locked: str | None = None  # why it cannot be toggled right now


# (selection after the press, pressed value, now checked) -> (selection to show, message or None)
Toggle = Callable[[list[str], str, bool], tuple[list[str], str | None]]
# selection -> {value: lock reason or None}
Locks = Callable[[list[str]], dict[str, str | None]]


class Prompter(Protocol):
    def checkbox(self, message: str, items: list[Item], *, minimum: int = 0, toggle: Toggle | None = None,
                 locks: Locks | None = None) -> Any: ...

    def text(self, message: str, *, default: str = "", check: Callable[[str], str | None] | None = None) -> Any: ...

    def select(self, message: str, choices: list[tuple[str, str]]) -> Any: ...


def _back(only_when_empty: bool = False) -> KeyBindings:
    kb = KeyBindings()
    empty = Condition(lambda: get_app().current_buffer.text == "")

    @kb.add("left", eager=True, filter=empty if only_when_empty else True)
    def _(event):
        event.app.exit(result=BACK)

    return kb


def _ask(question: questionary.Question, kb: KeyBindings):
    app = question.application
    app.key_bindings = merge_key_bindings([app.key_bindings, kb])
    answer = question.ask()
    if answer is None:  # Ctrl+C
        raise KeyboardInterrupt
    return answer


class QuestionaryPrompter:
    def checkbox(self, message, items, *, minimum=0, toggle=None, locks=None):
        state = {"selected": [i.value for i in items if i.checked]}

        def enough(_answer) -> bool | str:
            return True if len(state["selected"]) >= minimum else f"최소 {minimum}개를 선택하세요"

        question = questionary.checkbox(
            message,
            choices=[questionary.Choice(i.title, value=i.value, checked=i.checked, disabled=i.locked) for i in items],
            validate=enough,
            instruction="(space: 선택/해제, enter: 다음, ←: 이전)",
        )
        kb = _back()
        control = next(c for c in question.application.layout.find_all_controls() if isinstance(c, qc.InquirerControl))

        @kb.add(" ", eager=True)
        def _(event):
            choice = control.get_pointed_at()
            if choice.disabled:
                return
            now = choice.value not in state["selected"]
            selection = [v for v in state["selected"] if v != choice.value] + ([choice.value] if now else [])
            message_ = None
            if toggle is not None:
                selection, message_ = toggle(selection, choice.value, now)
            state["selected"] = selection
            control.selected_options = list(selection)
            if locks is not None:
                reasons = locks(selection)
                for c in control.choices:
                    if c.value in reasons:
                        c.disabled = reasons[c.value]
            control.error_message = FormattedText([("class:validation-toolbar", message_)]) if message_ else None

        @kb.add("a", eager=True)  # select-all / invert would skip the rules above
        @kb.add("i", eager=True)
        def _(event):
            pass

        answer = _ask(question, kb)
        return BACK if answer is BACK else list(dict.fromkeys(state["selected"]))

    def text(self, message, *, default="", check=None):
        def valid(value: str) -> bool | str:
            error = check(value) if check else None
            return True if error is None else error

        question = questionary.text(message, default=default, validate=valid, instruction="(←: 비어 있을 때 이전)")
        return _ask(question, _back(only_when_empty=True))

    def select(self, message, choices):
        question = questionary.select(message, choices=[questionary.Choice(title, value=v) for v, title in choices],
                                      instruction="(←: 이전)")
        return _ask(question, _back())

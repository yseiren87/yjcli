"""Prompt widgets: checkbox ([x]/[ ]), text and select, all with ← = back.

`Prompter` is the seam the wizard talks to; tests swap in a scripted fake.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

import questionary
import questionary.prompts.common as q_common
from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from questionary.prompts.common import InquirerControl

BACK = object()  # sentinel: user pressed ← (go to previous step)

q_common.INDICATOR_SELECTED = "[x]"
q_common.INDICATOR_UNSELECTED = "[ ]"


@dataclass
class Item:
    value: str
    title: str
    checked: bool = False
    disabled: str | None = None  # reason shown next to a locked item


# Called after a toggle with (current selection, toggled value, now_checked);
# returns (new selection, message to show or None).
OnToggle = Callable[[list[str], str, bool], tuple[list[str], str | None]]
# Called with the current selection; returns {value: reason it is disabled, or None}.
DisabledFor = Callable[[list[str]], dict[str, str | None]]


class Prompter(Protocol):
    def checkbox(self, message: str, items: list[Item], *, minimum: int = 0,
                 on_toggle: OnToggle | None = None, disabled_for: DisabledFor | None = None,
                 instruction: str | None = None) -> Any: ...

    def text(self, message: str, *, default: str = "",
             validate: Callable[[str], str | None] | None = None) -> Any: ...

    def select(self, message: str, choices: list[tuple[str, str]]) -> Any: ...


def _back_binding(only_when_empty: bool = False) -> KeyBindings:
    kb = KeyBindings()
    empty = Condition(lambda: get_app().current_buffer.text == "")

    @kb.add("left", eager=True, filter=empty if only_when_empty else True)
    def _(event):
        event.app.exit(result=BACK)

    return kb


def _attach(question: questionary.Question, kb: KeyBindings) -> questionary.Question:
    app = question.application
    app.key_bindings = merge_key_bindings([app.key_bindings, kb])
    return question


class QuestionaryPrompter:
    def checkbox(self, message, items, *, minimum=0, on_toggle=None, disabled_for=None, instruction=None):
        choices = [
            questionary.Choice(title=i.title, value=i.value, checked=i.checked, disabled=i.disabled)
            for i in items
        ]
        locked = [i.value for i in items if i.disabled and i.checked]

        def validate(selected: list[str]) -> bool | str:
            if len(selected) + len(locked) < minimum:
                return f"최소 {minimum}개를 선택하세요"
            return True

        question = questionary.checkbox(
            message,
            choices=choices,
            validate=validate,
            instruction=instruction or "(space: 선택/해제, a: 전체, enter: 다음, ←: 이전)",
        )
        kb = _back_binding()
        # Selection as the toggle rules see it; items locked on mid-way (disabled and
        # selected) are added to the answer, like the initially locked ones.
        current = {"selected": [i.value for i in items if i.checked]}
        control = None
        if on_toggle is not None:
            control = next(
                c for c in question.application.layout.find_all_controls() if isinstance(c, InquirerControl)
            )

            @kb.add(" ", eager=True)
            def _(event):
                value = control.get_pointed_at().value
                if control.get_pointed_at().disabled:
                    return
                now = value not in current["selected"]
                selection = [v for v in current["selected"] if v != value] + ([value] if now else [])
                updated, msg = on_toggle(selection, value, now)
                current["selected"] = updated
                control.selected_options = list(updated)
                if disabled_for is not None:
                    reasons = disabled_for(updated)
                    for choice in control.choices:
                        if choice.value in reasons:
                            choice.disabled = reasons[choice.value]
                control.error_message = FormattedText([("class:validation-toolbar", msg)]) if msg else None

            # Select-all / invert would bypass the dependency rules above.
            @kb.add("a", eager=True)
            @kb.add("i", eager=True)
            def _(event):
                pass

        answer = _attach(question, kb).ask()
        if answer is None:
            raise KeyboardInterrupt
        if answer is BACK:
            return BACK
        if control is not None:
            # Our own record is the truth (questionary may drop disabled entries).
            return list(dict.fromkeys(current["selected"]))
        return [*locked, *[v for v in answer if v not in locked]]

    def text(self, message, *, default="", validate=None):
        def check(value: str) -> bool | str:
            if validate is None:
                return True
            err = validate(value)
            return True if err is None else err

        question = questionary.text(message, default=default, validate=check,
                                    instruction="(←: 입력이 비어 있을 때 이전)")
        answer = _attach(question, _back_binding(only_when_empty=True)).ask()
        if answer is None:
            raise KeyboardInterrupt
        return answer

    def select(self, message, choices):
        question = questionary.select(
            message,
            choices=[questionary.Choice(title=title, value=value) for value, title in choices],
            instruction="(←: 이전)",
        )
        answer = _attach(question, _back_binding()).ask()
        if answer is None:
            raise KeyboardInterrupt
        return answer

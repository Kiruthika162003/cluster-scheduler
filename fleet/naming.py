"""Names: the rules are boring because names outlive everything else.

Lowercase letters, digits, single hyphens, starts with a letter, at
most 63 characters. That is the whole law, and every refusal explains
which rule and where, because a name rejected with a regex is a
support ticket and a name rejected with "position 4: double hyphen"
is a fixed typo. The sanitiser turns arbitrary text into a legal name
deterministically for machines that generate names from user input.
"""

from __future__ import annotations

from fleet.errors import Invalid

LIMIT = 63
LETTERS = set("abcdefghijklmnopqrstuvwxyz")
DIGITS = set("0123456789")


def check(name: str) -> None:
    if not name:
        raise Invalid("a name cannot be empty")
    if len(name) > LIMIT:
        raise Invalid(f"{len(name)} characters, the limit is {LIMIT}")
    if name[0] not in LETTERS:
        raise Invalid(f"position 1: must start with a letter, got {name[0]!r}")
    previous = ""
    for at, char in enumerate(name, start=1):
        if char in LETTERS or char in DIGITS:
            previous = char
            continue
        if char == "-":
            if previous == "-":
                raise Invalid(f"position {at}: double hyphen")
            previous = char
            continue
        raise Invalid(f"position {at}: {char!r} is not allowed")
    if name.endswith("-"):
        raise Invalid("a name cannot end with a hyphen")


def is_legal(name: str) -> bool:
    try:
        check(name)
    except Invalid:
        return False
    return True


def sanitise(text: str) -> str:
    cleaned = []
    previous = ""
    for char in text.lower():
        if char in LETTERS or char in DIGITS:
            cleaned.append(char)
            previous = char
        elif previous and previous != "-":
            cleaned.append("-")
            previous = "-"
    while cleaned and (cleaned[0] not in LETTERS):
        cleaned.pop(0)
    while cleaned and cleaned[-1] == "-":
        cleaned.pop()
    name = "".join(cleaned)[:LIMIT]
    while name.endswith("-"):
        name = name[:-1]
    if not name:
        raise Invalid(f"nothing legal survives in {text!r}")
    return name

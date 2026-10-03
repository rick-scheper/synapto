"""Parse ``decisions.md`` (spec §5.3) into one record per decision.

The template is a ``## <title>`` section per decision with ``**Context:**``,
``**Options:**``, ``**Chosen:**``, ``**Why:**``, ``**Trade-offs:**`` and
``**ADR:**`` fields. The validator doesn't enforce it, so parsing is lenient:
anything it can't place stays available as the section's raw Markdown, and a
file without sections (the "no decisions were made" case) becomes a note.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

_SECTION = re.compile(r"^##[ \t]+(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)
_FIELD = re.compile(r"^\*\*(Context|Options|Chosen|Why|Trade-offs|ADR):?\*\*:?[ \t]*", re.MULTILINE | re.IGNORECASE)
# "A — text", "(C — text)"; the dash may be an em dash, en dash or hyphen.
_OPTION = re.compile(r"^\(?\s*([A-Za-z0-9]{1,3})\s*[—–-]\s*(.+?)\s*\)?\.?$", re.DOTALL)


class DecisionOption(BaseModel):
    id: str
    label: str


class Decision(BaseModel):
    title: str
    context: str | None = None
    options: list[DecisionOption] = []
    chosen: str | None = None
    why: str | None = None
    tradeoffs: str | None = None
    adr: str | None = None
    body: str
    """The section's Markdown without its heading, for when the fields don't parse."""


class Decisions(BaseModel):
    decisions: list[Decision]
    note: str | None = None
    """Text before the first section, e.g. "No architectural decisions were made."."""


def parse_decisions(text: str) -> Decisions:
    sections = list(_SECTION.finditer(text))
    intro = text[: sections[0].start()] if sections else text
    intro = re.sub(r"^#[ \t].*$", "", intro, flags=re.MULTILINE).strip()  # drop a "# Decisions" title
    decisions = []
    for i, match in enumerate(sections):
        end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
        decisions.append(_parse_section(match[1], text[match.end():end].strip()))
    return Decisions(decisions=decisions, note=intro or None)


def _parse_section(title: str, body: str) -> Decision:
    fields: dict[str, str] = {}
    marks = list(_FIELD.finditer(body))
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        fields[mark[1].lower()] = " ".join(body[mark.end():end].split())

    options = _parse_options(fields.get("options", ""))
    chosen = fields.get("chosen")
    if chosen and options:
        # "B", "B — dict accumulation", "Option B"
        ids = {o.id.lower(): o.id for o in options}
        head = re.match(r"^(?:option\s+)?([A-Za-z0-9]{1,3})\b", chosen, re.IGNORECASE)
        chosen = ids.get(head[1].lower()) if head else None
    elif not options:
        chosen = None

    return Decision(
        title=title, context=fields.get("context"), options=options, chosen=chosen,
        why=fields.get("why"), tradeoffs=fields.get("trade-offs"), adr=fields.get("adr"), body=body,
    )


def _parse_options(text: str) -> list[DecisionOption]:
    options = []
    for part in (p.strip() for p in text.split(";")):
        match = _OPTION.match(part)
        if match is None:
            return []  # one unrecognised part means the list isn't in the template's shape
        options.append(DecisionOption(id=match[1], label=match[2]))
    return options

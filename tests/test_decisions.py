"""Parsing decisions.md (spec §5.3) for the Decisions tab."""

from synapto.bundle.decisions import parse_decisions

TEMPLATE = """# Decisions

## Spatial index for downsampling

**Context:** points must be grouped per voxel.
Clouds are 1–50 M points.
**Options:** A — a real octree; B — hash of integer voxel keys with `np.unique`; (C — scipy.spatial.cKDTree)
**Chosen:** B — voxel keys
**Why:** one vectorised pass.
**Trade-offs:** no neighbour queries.
**ADR:** docs/adr/0007-voxel-keys.md

## Which point represents a voxel

**Context:** each voxel becomes one point.
**Options:** A - the mean; B - the nearest point
**Chosen:** A
"""


def test_template_sections_become_decisions() -> None:
    parsed = parse_decisions(TEMPLATE)

    assert parsed.note is None
    first, second = parsed.decisions
    assert first.title == "Spatial index for downsampling"
    assert first.context == "points must be grouped per voxel. Clouds are 1–50 M points."
    assert [(o.id, o.label) for o in first.options] == [
        ("A", "a real octree"),
        ("B", "hash of integer voxel keys with `np.unique`"),
        ("C", "scipy.spatial.cKDTree"),
    ]
    assert first.chosen == "B"
    assert first.why == "one vectorised pass."
    assert first.tradeoffs == "no neighbour queries."
    assert first.adr == "docs/adr/0007-voxel-keys.md"
    assert [o.label for o in second.options] == ["the mean", "the nearest point"]
    assert second.chosen == "A"
    assert second.why is None


def test_no_decisions_is_a_note() -> None:
    parsed = parse_decisions("No architectural decisions were made in this build.\n")

    assert parsed.decisions == []
    assert parsed.note == "No architectural decisions were made in this build."


def test_free_form_section_keeps_its_markdown() -> None:
    body = "We kept the existing parser; nothing else was considered."
    [decision] = parse_decisions(f"## Keep the parser\n\n{body}\n").decisions

    assert decision.options == []
    assert decision.chosen is None
    assert decision.body == body


def test_options_outside_the_template_are_not_guessed() -> None:
    [decision] = parse_decisions("## X\n\n**Options:** sorting, or a dict\n**Chosen:** a dict\n").decisions

    assert decision.options == []
    assert decision.chosen is None

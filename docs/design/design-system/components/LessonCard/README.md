# LessonCard

LessonCard is one lesson in the Library grid.

**Props:** `title`, `summary` (clamped to 2 lines), `date`, `difficulty`, `concepts` (string[] → accent badges), `progress` (0…1), `stale` (bool → warning badge), `repo` (shown in mono at the foot).

- Fixed 340px in previews; in the grid, columns are `minmax(320px, 1fr)` with `space-4` gaps.
- The whole card is the link; hover lifts the border to `line-strong`, never a shadow or glow.
- Show at most 4 concept badges; summarise the rest as "+2".

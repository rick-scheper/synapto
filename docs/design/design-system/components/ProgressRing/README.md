# ProgressRing

ProgressRing shows how much of a lesson is done (quiz answered + exercises passed).

**Props:** `value` — 0…1; `size` — px (default 40); `stroke` — px (default 4); `showLabel` — bool (default true; hidden below 36px).

- Track `line`, fill `accent`; at 100% the fill turns `success` and the label becomes ✓.
- Used on LessonCard and in the lesson header. Not for loading spinners.

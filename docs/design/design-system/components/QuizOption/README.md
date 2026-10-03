# QuizOption

QuizOption is one answer row in a quiz question.

**Props:** `optionId` ("a"…"d"), `children` (the answer text), `state` — `idle` | `selected` | `correct` | `wrong`; `onClick`; `disabled`.

- Full width, stacked with `space-2` gaps under the question (`h2`).
- After answering: the chosen option becomes `correct` or `wrong`, the right one `correct`, the rest `idle` + `disabled`; then show the explanation below.
- Results carry ✓/✕ and the words "Correct" / "Not quite" — never colour alone.

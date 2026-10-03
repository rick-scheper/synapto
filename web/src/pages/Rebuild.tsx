// Rebuild tab (spec §12): rewrite a key function from its stub until the tests
// pass. The editor's code is saved as a draft while you type; "Run tests" grades
// it with pytest in the project venv (ADR-0004) and records the attempt. Hints
// open one at a time, and the solution after 3 attempts.

import { useCallback, useEffect, useRef, useState } from "react";
import { api, fileUrl, useLoad, type ExerciseState, type RunResult } from "../api";
import { CodeEditor } from "../components/CodeEditor";
import { Markdown } from "../components/Markdown";
import { Badge, Button, Callout, Status, TestResult } from "../components/ui";
import { plural, timeAgo } from "../format";

const SAVE_DELAY_MS = 800;
const SOLUTION_AFTER = 3;

export function RebuildTab({ lessonId, onProgress }: { lessonId: string; onProgress: () => void }) {
  const exercises = useLoad(() => api.exercises(lessonId), [lessonId]);
  const [current, setCurrent] = useState<string>();

  if (!exercises.data) return <Status error={exercises.error} />;
  const list = exercises.data;
  // Start at the first exercise that hasn't passed yet.
  const selected = list.find((e) => e.exercise.id === current) ?? list.find((e) => !e.passed) ?? list[0];
  if (!selected) return <Status>This lesson has no exercises.</Status>;
  const index = list.indexOf(selected);

  return (
    <div className="with-sidebar notebook-layout">
      <ExerciseView
        key={selected.exercise.id}
        lessonId={lessonId}
        state={selected}
        number={index + 1}
        total={list.length}
        onRan={() => {
          // Stay on this exercise even when it has just passed.
          setCurrent(selected.exercise.id);
          exercises.reload();
          onProgress();
        }}
        onNext={index + 1 < list.length ? () => setCurrent(list[index + 1].exercise.id) : undefined}
      />
      <aside className="sidebar stack-5">
        <nav className="question-list" aria-label="Exercises">
          <h2 className="overline ink">Exercises</h2>
          {list.map((e) => {
            const isCurrent = e === selected;
            const last = e.runs.at(-1);
            return (
              <button
                key={e.exercise.id}
                type="button"
                className={`question-row${isCurrent ? " is-current" : ""}${e.passed ? " is-done" : ""}`}
                onClick={() => setCurrent(e.exercise.id)}
              >
                <span className={`question-mark ${e.passed ? "ok" : ""}`} aria-hidden>
                  {e.passed ? "✓" : isCurrent ? "•" : ""}
                </span>
                <span className="grow">{e.exercise.title}</span>
                <span className="caption muted">
                  {e.passed ? "Passed" : last ? `${last.n_passed} of ${last.n_total}` : "Not started"}
                </span>
              </button>
            );
          })}
        </nav>
        {selected.runs.length > 0 && (
          <section className="question-list" aria-label="Attempts">
            <h2 className="overline ink">Attempts</h2>
            {selected.runs
              .map((run, i) => ({ run, n: i + 1 }))
              .reverse()
              .map(({ run, n }) => (
                <div key={n} className="attempt-row">
                  <span className="grow">
                    Attempt {n} · {timeAgo(run.ran_at)}
                  </span>
                  <span className={`caption strong ${run.passed ? "ok" : "bad"}`}>
                    {run.passed ? "✓" : "✕"} {run.n_total ? `${run.n_passed} of ${run.n_total}` : "Didn't run"}
                  </span>
                </div>
              ))}
          </section>
        )}
      </aside>
    </div>
  );
}

function ExerciseView({
  lessonId,
  state,
  number,
  total,
  onRan,
  onNext,
}: {
  lessonId: string;
  state: ExerciseState;
  number: number;
  total: number;
  onRan: () => void;
  onNext?: () => void;
}) {
  const { exercise, stub } = state;
  const draft = useLoad(() => api.draft(lessonId, exercise.id), [lessonId, exercise.id]);
  const [code, setCode] = useState<string>();
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [hints, setHints] = useState(0);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<RunResult>();
  const [runError, setRunError] = useState<Error>();
  const [solution, setSolution] = useState<string>();

  useEffect(() => {
    if (draft.data && code === undefined) {
      setCode(draft.data.code);
      setSavedAt(draft.data.updated_at);
    }
  }, [draft.data, code]);

  // --- Saving the draft ---------------------------------------------------------
  const codeRef = useRef(code);
  codeRef.current = code;
  const saveTimer = useRef<number | undefined>(undefined);

  const save = useCallback(async () => {
    saveTimer.current = undefined;
    if (codeRef.current === undefined) return;
    try {
      setSavedAt((await api.saveDraft(lessonId, exercise.id, codeRef.current)).updated_at);
      setSaveError(null);
    } catch (err) {
      setSaveError((err as Error).message);
    }
  }, [lessonId, exercise.id]);
  const saveRef = useRef(save);
  saveRef.current = save;

  const edit = (value: string) => {
    setCode(value);
    window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => saveRef.current(), SAVE_DELAY_MS);
  };

  // Don't lose edits made just before switching exercise or tab.
  useEffect(
    () => () => {
      if (saveTimer.current !== undefined) {
        window.clearTimeout(saveTimer.current);
        saveRef.current();
      }
    },
    [],
  );

  // --- Running the tests ----------------------------------------------------------
  const run = async () => {
    if (code === undefined || running) return;
    // The run saves the code as the draft too.
    window.clearTimeout(saveTimer.current);
    saveTimer.current = undefined;
    setRunning(true);
    setRunError(undefined);
    try {
      const outcome = await api.runTests(lessonId, exercise.id, code);
      setResult(outcome);
      setSavedAt(outcome.ran_at);
      setSaveError(null);
      onRan();
    } catch (err) {
      setRunError(err as Error);
    } finally {
      setRunning(false);
    }
  };

  const attempts = state.runs.length;
  const canSeeSolution = attempts >= SOLUTION_AFTER || state.passed;
  const showSolution = async () => {
    try {
      const response = await fetch(fileUrl(lessonId, `exercises/${exercise.id}/solution.py`));
      if (!response.ok) throw new Error(`Couldn't load the solution (${response.status})`);
      setSolution(await response.text());
    } catch (err) {
      setRunError(err as Error);
    }
  };

  const justPassed = result?.passed === true;

  return (
    <div className="notebook rebuild">
      <section className="stack-2">
        <div className="row-2">
          <span className="overline">
            Exercise {number} of {total}
          </span>
          <Badge>{exercise.difficulty}</Badge>
          {state.passed && <Badge tone="success">Passed</Badge>}
        </div>
        <h2 className="h2">{exercise.title}</h2>
        <div className="rebuild-prompt">
          <Markdown text={exercise.prompt} lessonId={lessonId} />
        </div>
      </section>

      {exercise.hints.length > 0 && (
        <section className="stack-2" aria-label="Hints">
          {exercise.hints.slice(0, hints).map((hint, i) => (
            <Callout key={i} title={`Hint ${i + 1} of ${exercise.hints.length}`}>
              <Markdown text={hint} lessonId={lessonId} inline />
            </Callout>
          ))}
          {hints < exercise.hints.length && (
            <div>
              <Button variant="ghost" size="sm" onClick={() => setHints((h) => h + 1)}>
                {hints === 0 ? "Show a hint" : "Show next hint"}
              </Button>
            </div>
          )}
        </section>
      )}

      <section className="stack-2">
        <div className="rebuild-editor-head">
          <span className="mono-sm">candidate.py</span>
          <span className="caption muted">
            {saveError
              ? "Draft not saved"
              : savedAt
                ? `Draft saved${attempts ? ` · ${plural(attempts, "attempt")}` : ""}`
                : "Starting from the stub"}
          </span>
        </div>
        <section className={`sy-cell${running ? " is-running" : ""}`}>
          <header className="sy-cell-head">
            <span className="sy-overline sy-cell-role">function · </span>
            <span className="sy-cell-fn">{exercise.function}</span>
            <span className="sy-cell-spacer" />
            <span className="sy-cell-ref">{exercise.source_ref}</span>
            {running && (
              <span className="sy-cell-live">
                <span className="sy-dot" />
                Running tests
              </span>
            )}
          </header>
          <div className="sy-cell-code">
            {code === undefined ? (
              <Status error={draft.error} />
            ) : (
              <CodeEditor value={code} onChange={edit} onRun={run} label={`Your ${exercise.function}`} />
            )}
          </div>
        </section>
        {saveError && (
          <Callout tone="warning" title="Your draft couldn't be saved">
            {saveError}
          </Callout>
        )}
        <div className="rebuild-actions">
          <Button variant="primary" icon="▶" onClick={run} disabled={code === undefined || running}>
            {running ? "Running tests…" : "Run tests"}
          </Button>
          <Button onClick={() => edit(stub)} disabled={code === undefined || code === stub || running}>
            Reset to stub
          </Button>
          <span className="grow" />
          <Button variant="ghost" onClick={showSolution} disabled={!canSeeSolution || solution !== undefined}>
            Show solution
          </Button>
          {!canSeeSolution && (
            <span className="caption muted">
              Available after {SOLUTION_AFTER} attempts ({SOLUTION_AFTER - attempts} to go)
            </span>
          )}
        </div>
      </section>

      {runError && <Status error={runError} />}
      {result &&
        (result.error ? (
          <Callout tone="danger" title="The tests couldn't run against your code">
            <pre className="sy-test-msg">{result.error}</pre>
          </Callout>
        ) : (
          <TestResult tests={result.tests} glow={justPassed} />
        ))}
      {justPassed && (
        <Callout
          tone="success"
          title={`Every test passes — you rebuilt ${exercise.function}.`}
          action={
            onNext && (
              <Button onClick={onNext}>
                Next exercise
              </Button>
            )
          }
        />
      )}

      {solution !== undefined && (
        <section className="stack-2" aria-label="Solution">
          <div className="rebuild-editor-head">
            <span className="mono-sm">solution.py</span>
            <span className="caption muted">The reference implementation, read-only</span>
          </div>
          <section className="sy-cell">
            <div className="sy-cell-code">
              <CodeEditor value={solution} readOnly label={`Solution for ${exercise.function}`} />
            </div>
          </section>
          <div>
            <Button size="sm" variant="ghost" onClick={() => setSolution(undefined)}>
              Hide solution
            </Button>
          </div>
        </section>
      )}
    </div>
  );
}

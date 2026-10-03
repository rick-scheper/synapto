// Notebook tab (spec §12): the lesson's notebook running in a kernel in the
// project's own venv. Cells can be edited and run one by one or all at once;
// edits and outputs are saved as the learner's working copy, which "Reset to
// original" discards. The data slot panel points the setup cells at the
// learner's own files, and applying it restarts the kernel.

import { Play, RotateCcw, Square, Undo2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  api,
  ApiError,
  useLoad,
  type DataValue,
  type Lesson,
  type Notebook,
  type NotebookCell,
  type NotebookState,
  type SlotState,
} from "../api";
import { CodeEditor } from "../components/CodeEditor";
import { Markdown } from "../components/Markdown";
import { Outputs } from "../components/Outputs";
import { Button, Callout, Status, TextField } from "../components/ui";
import { applyEvent, joinText, KernelSocket, savedOutputs, updateDisplay, type LiveOutput } from "../kernel";

type CellStatus = "idle" | "queued" | "running" | "done" | "error";

interface Cell {
  key: string;
  /** The cell as loaded, for the fields the hub doesn't change (id, metadata, attachments). */
  raw: NotebookCell;
  source: string;
  outputs: LiveOutput[];
  clearPending: boolean;
  executionCount: number | null;
  status: CellStatus;
  /** Seconds the last run took. */
  elapsed?: number;
}

type KernelState = { phase: "starting" } | { phase: "ready" } | { phase: "failed"; message: string };

const SAVE_DELAY_MS = 800;
const NEW_SESSION =
  "The kernel was restarted since your last run (it shuts down after 30 idle minutes), so earlier results are gone. " +
  "Run all to rebuild them.";

let nextKey = 0;

function toCells(notebook: Notebook): Cell[] {
  return notebook.cells.map((raw) => ({
    key: `c${++nextKey}`,
    raw,
    source: joinText(raw.source),
    outputs: raw.outputs ?? [],
    clearPending: false,
    executionCount: raw.execution_count ?? null,
    status: "idle",
  }));
}

function toNotebook(base: Notebook, cells: Cell[]): Notebook {
  return {
    ...base,
    cells: cells.map(({ raw, source, outputs, executionCount }) =>
      raw.cell_type === "code"
        ? { ...raw, source, outputs: savedOutputs(outputs), execution_count: executionCount }
        : { ...raw, source },
    ),
  };
}

const meta = (cell: Cell) => cell.raw.metadata.debrief;
const isCode = (cell: Cell) => cell.raw.cell_type === "code";

export function NotebookTab({ lesson }: { lesson: Lesson }) {
  const notebook = useLoad(() => api.notebook(lesson.id), [lesson.id]);
  if (!notebook.data) return <Status error={notebook.error} />;
  return <NotebookView key={lesson.id} lesson={lesson} initial={notebook.data} />;
}

function NotebookView({ lesson, initial }: { lesson: Lesson; initial: NotebookState }) {
  const lessonId = lesson.id;
  const [cells, setCells] = useState(() => toCells(initial.notebook));
  const [base, setBase] = useState(initial.notebook);
  const [modified, setModified] = useState(initial.modified);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [kernel, setKernel] = useState<KernelState>({ phase: "starting" });
  const [notice, setNotice] = useState<string | null>(null);

  const cellsRef = useRef(cells);
  cellsRef.current = cells;
  const socket = useRef<KernelSocket | null>(null);
  const session = useRef<string | null>(null);
  // Bumped by interrupt, restart and reset: queued runs from before then are dropped.
  const generation = useRef(0);
  const chain = useRef<Promise<void>>(Promise.resolve());
  const saveTimer = useRef<number | undefined>(undefined);

  const update = (key: string, change: (cell: Cell) => Cell) =>
    setCells((cs) => cs.map((c) => (c.key === key ? change(c) : c)));

  // --- Saving the working copy ------------------------------------------------
  const save = useCallback(async () => {
    saveTimer.current = undefined;
    try {
      await api.saveNotebook(lessonId, toNotebook(base, cellsRef.current));
      setModified(true);
      setSaveError(null);
    } catch (err) {
      setSaveError((err as Error).message);
    }
  }, [lessonId, base]);
  const saveRef = useRef(save);
  saveRef.current = save;

  const scheduleSave = () => {
    window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => saveRef.current(), SAVE_DELAY_MS);
  };

  // --- Kernel -------------------------------------------------------------------
  const startKernel = useCallback(
    async (restart: boolean) => {
      setKernel({ phase: "starting" });
      try {
        const info = await (restart ? api.restartKernel(lessonId) : api.startKernel(lessonId));
        session.current = info.session;
        setKernel({ phase: "ready" });
      } catch (err) {
        setKernel({ phase: "failed", message: (err as Error).message });
      }
    },
    [lessonId],
  );

  useEffect(() => {
    const s = new KernelSocket(lessonId);
    socket.current = s;
    startKernel(false);
    return () => {
      s.close();
      // Don't lose edits made just before leaving the tab.
      if (saveTimer.current !== undefined) {
        window.clearTimeout(saveTimer.current);
        saveRef.current();
      }
    };
  }, [lessonId, startKernel]);

  const unqueue = () => setCells((cs) => cs.map((c) => (c.status === "queued" ? { ...c, status: "idle" } : c)));
  const stopQueue = () => {
    generation.current++;
    unqueue();
  };

  const runOne = async (key: string, gen: number): Promise<boolean> => {
    const cell = cellsRef.current.find((c) => c.key === key);
    if (!cell || !socket.current) return false;
    const started = performance.now();
    update(key, (c) => ({ ...c, status: "running", outputs: [], clearPending: false, elapsed: undefined }));
    const done = await socket.current.execute(cell.source, (event) => {
      if (event.type === "kernel") {
        if (session.current && event.session !== session.current) setNotice(NEW_SESSION);
        session.current = event.session;
        setKernel({ phase: "ready" });
      } else if (event.type === "display" && event.update) {
        setCells((cs) => cs.map((c) => ({ ...c, outputs: updateDisplay(c.outputs, event) })));
      } else {
        update(key, (c) => ({ ...c, ...applyEvent(c, event) }));
      }
    });
    const ok = done.status === "ok";
    update(key, (c) => ({
      ...c,
      status: ok ? "done" : "error",
      executionCount: done.execution_count ?? c.executionCount,
      elapsed: (performance.now() - started) / 1000,
    }));
    if (gen === generation.current) scheduleSave();
    return ok;
  };

  /** Run cells in order, after anything already running; stop at the first that fails. */
  const run = (keys: string[]) => {
    const gen = generation.current;
    setCells((cs) => cs.map((c) => (keys.includes(c.key) ? { ...c, status: "queued" } : c)));
    chain.current = chain.current.then(async () => {
      for (const key of keys) {
        if (gen !== generation.current) return;
        if (!(await runOne(key, gen))) {
          if (gen === generation.current) unqueue();
          return;
        }
      }
    });
  };

  const runAll = () => {
    setNotice(null);
    run(cellsRef.current.filter(isCode).map((c) => c.key));
  };

  const interrupt = () => {
    stopQueue();
    socket.current?.interrupt();
  };

  const restart = async (message: string | null = null) => {
    stopQueue();
    await startKernel(true);
    setNotice(message);
  };

  const reset = async () => {
    if (!window.confirm("Discard your edits and outputs, and restart the kernel with the original notebook?")) return;
    stopQueue();
    window.clearTimeout(saveTimer.current);
    saveTimer.current = undefined;
    try {
      const state = await api.resetNotebook(lessonId);
      setBase(state.notebook);
      setCells(toCells(state.notebook));
      setModified(false);
      setSaveError(null);
    } catch (err) {
      setSaveError((err as Error).message);
      return;
    }
    await restart();
  };

  const edit = (key: string, source: string) => {
    update(key, (c) => ({ ...c, source }));
    scheduleSave();
  };

  const highlighted = useSourceRefTarget(cells);
  const busy = cells.some((c) => c.status === "running" || c.status === "queued");
  const visible = cells.filter((c) => !meta(c)?.hidden);

  return (
    <div className="with-sidebar notebook-layout">
      <div className="notebook">
        <div className="nb-toolbar">
          <Button variant="primary" size="sm" icon={<Play size={12} />} onClick={runAll} disabled={kernel.phase === "starting"}>
            Run all
          </Button>
          {busy && (
            <Button size="sm" icon={<Square size={12} />} onClick={interrupt}>
              Interrupt
            </Button>
          )}
          <Button size="sm" icon={<RotateCcw size={12} />} onClick={() => restart()} disabled={kernel.phase === "starting"}>
            Restart kernel
          </Button>
          <Button variant="ghost" size="sm" icon={<Undo2 size={12} />} onClick={reset} disabled={!modified} title="Discard your edits and outputs">
            Reset to original
          </Button>
          <span className="grow" />
          <KernelStatus lesson={lesson} kernel={kernel} busy={busy} />
        </div>

        {kernel.phase === "failed" && (
          <Callout
            tone="danger"
            title="The kernel didn't start"
            action={
              <Button size="sm" onClick={() => startKernel(false)}>
                Try again
              </Button>
            }
          >
            <span className="pre-wrap">{kernel.message}</span>
          </Callout>
        )}
        {notice && <Callout tone="info">{notice}</Callout>}
        {saveError && (
          <Callout tone="warning" title="Your changes couldn't be saved">
            {saveError}
          </Callout>
        )}

        {visible.map((cell) =>
          isCode(cell) ? (
            <CodeCellView
              key={cell.key}
              cell={cell}
              lessonId={lessonId}
              highlighted={highlighted === cell.key}
              onRun={() => run([cell.key])}
              onChange={(source) => edit(cell.key, source)}
            />
          ) : (
            <div key={cell.key} className="nb-explain">
              <Markdown text={cell.source} lessonId={lessonId} />
            </div>
          ),
        )}
      </div>

      <aside className="sidebar nb-sidebar stack-5">
        {lesson.data_slots.length > 0 && (
          <DataSlotsPanel lessonId={lessonId} onApplied={() => restart("Restarted with your data. Run all to load it.")} />
        )}
        <Outline cells={visible.filter(isCode)} />
      </aside>
    </div>
  );
}

function KernelStatus({ lesson, kernel, busy }: { lesson: Lesson; kernel: KernelState; busy: boolean }) {
  const { python, python_version, cwd } = lesson.environment;
  const shown = python.startsWith(cwd.replace(/\/?$/, "/")) ? python.slice(cwd.replace(/\/?$/, "/").length) : python;
  const label = kernel.phase === "starting" ? "Starting…" : kernel.phase === "failed" ? "No kernel" : busy ? "Busy" : "Idle";
  return (
    <span className={`nb-kernel is-${kernel.phase === "ready" ? (busy ? "busy" : "idle") : kernel.phase}`} title={python}>
      <span className="nb-kernel-dot" aria-hidden />
      <span className="label">{label}</span>
      <span className="mono-sm muted">
        {shown}
        {python_version && ` ${python_version}`}
      </span>
    </span>
  );
}

function CodeCellView({
  cell,
  lessonId,
  highlighted,
  onRun,
  onChange,
}: {
  cell: Cell;
  lessonId: string;
  highlighted: boolean;
  onRun: () => void;
  onChange: (source: string) => void;
}) {
  const m = meta(cell);
  const pending = cell.status === "running" || cell.status === "queued";
  const readOnly = m?.editable === false;
  return (
    <section id={`cell-${cell.key}`} className={`sy-cell is-${cell.status}${highlighted ? " is-target" : ""}`}>
      <header className="sy-cell-head">
        <span className="sy-cell-count">[{pending ? "*" : (cell.executionCount ?? " ")}]</span>
        {m?.role && (
          <span className="sy-overline sy-cell-role">
            {m.role}
            {m.function ? " · " : ""}
          </span>
        )}
        {m?.function && <span className="sy-cell-fn">{m.function}</span>}
        {readOnly && <span className="caption muted">read-only</span>}
        <span className="sy-cell-spacer" />
        {m?.source_ref && <span className="sy-cell-ref">{m.source_ref}</span>}
        {cell.status === "running" ? (
          <span className="sy-cell-live">
            <span className="sy-dot" />
            Running
          </span>
        ) : cell.status === "queued" ? (
          <span className="sy-cell-live muted">Queued</span>
        ) : (
          <Button size="sm" variant="ghost" icon="▶" onClick={onRun}>
            Run
          </Button>
        )}
      </header>
      <div className="sy-cell-code">
        <CodeEditor
          value={cell.source}
          onChange={onChange}
          onRun={onRun}
          readOnly={readOnly}
          label={`${m?.role ?? "code"} cell${m?.function ? ` ${m.function}` : ""}`}
        />
      </div>
      <Outputs outputs={cell.outputs} lessonId={lessonId} />
      {cell.elapsed !== undefined && !pending && <div className="sy-cell-time">Ran in {cell.elapsed.toFixed(2)} s</div>}
    </section>
  );
}

function Outline({ cells }: { cells: Cell[] }) {
  if (cells.length === 0) return null;
  const name = (cell: Cell) => {
    const m = meta(cell);
    if (m?.function) return m.function;
    const lines = cell.source.split("\n").map((l) => l.trim()).filter(Boolean);
    const comment = lines.find((l) => l.startsWith("#"));
    return (comment ? comment.replace(/^#+\s*/, "") : lines[0]) ?? "";
  };
  return (
    <nav className="outline nb-outline" aria-label="In this notebook">
      <h2 className="overline ink">In this notebook</h2>
      {cells.map((cell) => (
        <a
          key={cell.key}
          href={`#cell-${cell.key}`}
          className={cell.status === "running" ? "is-active" : undefined}
          onClick={(e) => {
            e.preventDefault();
            document.getElementById(`cell-${cell.key}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
          }}
        >
          <span className="nb-outline-role">{meta(cell)?.role ?? "code"}</span>
          <span className="nb-outline-name">{name(cell)}</span>
        </a>
      ))}
    </nav>
  );
}

function DataSlotsPanel({ lessonId, onApplied }: { lessonId: string; onApplied: () => void }) {
  const slots = useLoad(() => api.dataSlots(lessonId), [lessonId]);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [applying, setApplying] = useState(false);

  const saved = (slot: SlotState) => (slot.value === null ? "" : String(slot.value));
  useEffect(() => {
    if (slots.data) setDraft(Object.fromEntries(slots.data.map((s) => [s.name, saved(s)])));
  }, [slots.data]);

  if (!slots.data) return slots.error ? <Status error={slots.error} /> : null;
  const dirty = slots.data.some((s) => (draft[s.name] ?? "") !== saved(s));

  const apply = async () => {
    const values: Record<string, DataValue | null> = {};
    for (const slot of slots.data!) {
      const text = (draft[slot.name] ?? "").trim();
      // A number field that doesn't parse goes to the server as text, which explains the problem.
      values[slot.name] = text === "" ? null : slot.kind === "number" && Number.isFinite(Number(text)) ? Number(text) : text;
    }
    setApplying(true);
    try {
      await api.saveDataSlots(lessonId, values);
      setErrors({});
      slots.reload();
      onApplied();
    } catch (err) {
      const detail = err instanceof ApiError ? (err.detail as { errors?: Record<string, string> }) : undefined;
      setErrors(detail?.errors ?? { "": (err as Error).message });
    } finally {
      setApplying(false);
    }
  };

  const placeholder = (slot: SlotState) =>
    slot.default === null
      ? slot.required
        ? "required"
        : "no default"
      : slot.kind === "file" || slot.kind === "dir"
        ? `${slot.default} (bundled sample)`
        : String(slot.default);

  return (
    <section className="panel nb-slots stack-4">
      <div className="stack-1">
        <h2 className="sy-h3">Data slots</h2>
        <span className="caption muted">Point the notebook at your own data. Leave a field empty to use the default.</span>
      </div>
      {slots.data.map((slot) => (
        <TextField
          key={slot.name}
          label={slot.name}
          mono
          value={draft[slot.name] ?? ""}
          onChange={(v) => setDraft((d) => ({ ...d, [slot.name]: v }))}
          placeholder={placeholder(slot)}
          hint={slot.description}
          error={errors[slot.name] ?? slot.error}
        />
      ))}
      {errors[""] && <span className="sy-field-error">✕ {errors[""]}</span>}
      <div>
        <Button size="sm" onClick={apply} disabled={!dirty || applying}>
          {applying ? "Applying…" : "Apply and restart"}
        </Button>
      </div>
    </section>
  );
}

/**
 * The cell a `#src=<path:lines>` link (from a code reference in the Explain tab)
 * points at: the cell with that exact `source_ref`, else one in the same file
 * whose lines overlap. It is scrolled into view and highlighted briefly.
 */
function useSourceRefTarget(cells: Cell[]): string | undefined {
  const { hash } = useLocation();
  const [target, setTarget] = useState<string>();
  const wanted = hash.startsWith("#src=") ? decodeURIComponent(hash.slice(5)) : null;

  useEffect(() => {
    if (!wanted) return;
    const key = findCell(cellsRefFor(cells), wanted);
    if (!key) return;
    setTarget(key);
    document.getElementById(`cell-${key}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    const timer = window.setTimeout(() => setTarget(undefined), 2400);
    return () => window.clearTimeout(timer);
    // Only when the link changes, not on every edit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wanted]);
  return target;
}

const cellsRefFor = (cells: Cell[]) =>
  cells.filter((c) => isCode(c) && !meta(c)?.hidden && meta(c)?.source_ref).map((c) => ({ key: c.key, ref: meta(c)!.source_ref! }));

function parseRef(ref: string): { path: string; from: number; to: number } | null {
  const m = /^(.+?):(\d+)(?:-(\d+))?$/.exec(ref.trim());
  return m ? { path: m[1], from: Number(m[2]), to: Number(m[3] ?? m[2]) } : null;
}

function findCell(cells: { key: string; ref: string }[], wanted: string): string | undefined {
  const exact = cells.find((c) => c.ref === wanted);
  if (exact) return exact.key;
  const w = parseRef(wanted);
  if (!w) return undefined;
  return cells.find((c) => {
    const r = parseRef(c.ref);
    return r && r.path === w.path && r.from <= w.to && w.from <= r.to;
  })?.key;
}

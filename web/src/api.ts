// Types and calls for the hub's HTTP API (spec §9.1). They mirror the pydantic
// models in src/synapto/server/ and src/synapto/bundle/.

import { useCallback, useEffect, useState } from "react";

export type Difficulty = "beginner" | "intermediate" | "advanced";

/** The parts a lesson can have, in the order the hub shows them. */
export const PARTS = ["explain", "decisions", "notebook", "quiz", "rebuild"] as const;
export type Part = (typeof PARTS)[number];

export interface Lesson {
  id: string;
  title: string;
  summary: string;
  created_at: string;
  difficulty: Difficulty;
  concepts: string[];
  prerequisites: string[];
  source: {
    repo_path: string;
    remote: string | null;
    branch: string | null;
    base_commit: string | null;
    head_commit: string | null;
    includes_uncommitted: boolean;
    files: { path: string; sha256: string }[];
  };
  environment: {
    python: string;
    python_version: string | null;
    cwd: string;
    extra_sys_path: string[];
  };
  data_slots: DataSlot[];
  /** The parts chosen at /debrief time; the hub shows a tab for each. */
  parts: Part[];
}

export type DataValue = string | number;

export interface DataSlot {
  name: string;
  kind: "file" | "dir" | "string" | "number";
  description: string;
  default: DataValue | null;
  required: boolean;
}

export interface SlotState extends DataSlot {
  /** The learner's value, or null to use the default. */
  value: DataValue | null;
  /** Why `value` can't be used, e.g. the file has since been deleted. */
  error: string | null;
}

export interface Progress {
  /** 0…1; 0 for a lesson without a quiz or rebuild part. */
  value: number;
  quiz: { answered: number; correct: number; total: number };
  exercises: { passed: number; total: number };
}

/** Whether the lesson has anything to complete: quiz questions or exercises. */
export const completable = (p: Progress) => p.quiz.total + p.exercises.total > 0;

export interface Staleness {
  stale: boolean;
  repo_missing: boolean;
  changed: { path: string; change: "modified" | "missing" }[];
}

export interface LessonSummary {
  id: string;
  title: string;
  summary: string;
  created_at: string;
  difficulty: Difficulty;
  concepts: string[];
  repo_path: string;
  branch: string | null;
  head_commit: string | null;
  progress: Progress;
  staleness: Staleness;
  opened_at: string | null;
}

export interface Answer {
  option_id: string;
  correct: boolean;
}

export interface LessonDetail {
  lesson: Lesson;
  progress: Progress;
  staleness: Staleness;
  answers: Record<string, Answer>;
}

export interface Decision {
  title: string;
  context: string | null;
  options: { id: string; label: string }[];
  chosen: string | null;
  why: string | null;
  tradeoffs: string | null;
  adr: string | null;
  body: string;
}

export interface Decisions {
  decisions: Decision[];
  note: string | null;
}

export interface QuizQuestion {
  id: string;
  prompt: string;
  options: { id: string; text: string }[];
  correct: string;
  explanation: string;
  concept: string | null;
  source_ref: string | null;
}

export interface Quiz {
  questions: QuizQuestion[];
}

export interface Exercise {
  id: string;
  title: string;
  function: string;
  prompt: string;
  difficulty: "easy" | "medium" | "hard";
  hints: string[];
  source_ref: string;
}

export interface ExerciseRun {
  /** Every test passed. */
  passed: boolean;
  n_passed: number;
  n_total: number;
  ran_at: string;
}

export interface ExerciseState {
  exercise: Exercise;
  /** `stub.py`, the code the editor starts from. */
  stub: string;
  /** Every test run, oldest first; their number is the attempt count. */
  runs: ExerciseRun[];
  /** Whether any run passed every test. */
  passed: boolean;
}

export interface Draft {
  /** The learner's in-progress code, else `stub.py`. */
  code: string;
  saved: boolean;
  updated_at: string | null;
}

export interface TestCase {
  name: string;
  status: "passed" | "failed" | "error" | "skipped";
  message: string;
}

export interface RunResult extends ExerciseRun {
  tests: TestCase[];
  /** Why pytest produced no per-test results, e.g. the code doesn't import. */
  error: string | null;
}

// nbformat 4 (ADR-0002). Multi-line strings may be stored as arrays of lines.
type MultiLine = string | string[];
export type MimeBundle = Record<string, MultiLine | object>;

export type Output =
  | { output_type: "stream"; name: "stdout" | "stderr"; text: MultiLine }
  | { output_type: "display_data"; data: MimeBundle; metadata: Record<string, unknown> }
  | { output_type: "execute_result"; data: MimeBundle; metadata: Record<string, unknown>; execution_count: number | null }
  | { output_type: "error"; ename: string; evalue: string; traceback: string[] };

export interface CellMeta {
  role: "setup" | "function" | "demo" | "explain";
  function?: string | null;
  source_ref?: string | null;
  hidden?: boolean;
  editable?: boolean;
}

export interface NotebookCell {
  id?: string;
  cell_type: "code" | "markdown" | "raw";
  source: MultiLine;
  metadata: { synapto?: CellMeta; [key: string]: unknown };
  outputs?: Output[];
  execution_count?: number | null;
  attachments?: unknown;
}

export interface Notebook {
  cells: NotebookCell[];
  metadata: Record<string, unknown>;
  nbformat: 4;
  nbformat_minor: number;
}

export interface NotebookState {
  /** The learner's working copy, else the original. */
  notebook: Notebook;
  modified: boolean;
  updated_at: string | null;
}

export interface KernelInfo {
  /** Changes whenever a new kernel process starts. */
  session: string;
  busy: boolean;
}

export interface Totals {
  lessons: number;
  in_progress: number;
  completed: number;
  stale: number;
  quiz: { answered: number; correct: number; total: number };
  concepts: { name: string; lessons: number }[];
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    /** The response's `detail`, e.g. per-field errors. */
    readonly detail?: unknown,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit, as: "json" | "text" = "json"): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      // not JSON
    }
    const message = typeof detail === "object" && detail && "message" in detail ? detail.message : detail;
    throw new ApiError(response.status, String(message), detail);
  }
  return (as === "json" ? response.json() : response.text()) as Promise<T>;
}

export const fileUrl = (lessonId: string, path: string) =>
  `/api/lessons/${encodeURIComponent(lessonId)}/files/${path.split("/").map(encodeURIComponent).join("/")}`;

const lessonPath = (id: string, rest = "") => `/api/lessons/${encodeURIComponent(id)}${rest}`;

const send = (method: string, body?: unknown): RequestInit => ({
  method,
  ...(body === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
});

export const api = {
  lessons: (concept?: string) =>
    request<LessonSummary[]>(`/api/lessons${concept ? `?concept=${encodeURIComponent(concept)}` : ""}`),
  lesson: (id: string) => request<LessonDetail>(`/api/lessons/${encodeURIComponent(id)}`),
  deleteLesson: (id: string) => request<void>(lessonPath(id), send("DELETE"), "text"),
  decisions: (id: string) => request<Decisions>(`/api/lessons/${encodeURIComponent(id)}/decisions`),
  text: (id: string, path: string) => request<string>(fileUrl(id, path), undefined, "text"),
  quiz: (id: string) => request<Quiz>(fileUrl(id, "quiz.json")),
  progress: () => request<Totals>("/api/progress"),
  answer: (id: string, questionId: string, optionId: string) =>
    request<{ correct: boolean; correct_option: string; explanation: string }>(
      `/api/lessons/${encodeURIComponent(id)}/quiz/${encodeURIComponent(questionId)}/answer`,
      send("POST", { option_id: optionId }),
    ),
  notebook: (id: string) => request<NotebookState>(lessonPath(id, "/notebook")),
  saveNotebook: (id: string, notebook: Notebook) =>
    request<NotebookState>(lessonPath(id, "/notebook"), send("PUT", { notebook })),
  resetNotebook: (id: string) => request<NotebookState>(lessonPath(id, "/notebook/reset"), send("POST")),
  dataSlots: (id: string) => request<SlotState[]>(lessonPath(id, "/data-slots")),
  saveDataSlots: (id: string, values: Record<string, DataValue | null>) =>
    request<SlotState[]>(lessonPath(id, "/data-slots"), send("PUT", { values })),
  startKernel: (id: string) => request<KernelInfo>(lessonPath(id, "/kernel"), send("POST")),
  restartKernel: (id: string) => request<KernelInfo>(lessonPath(id, "/kernel/restart"), send("POST")),
  exercises: (id: string) => request<ExerciseState[]>(lessonPath(id, "/exercises")),
  draft: (id: string, exerciseId: string) =>
    request<Draft>(lessonPath(id, `/exercises/${encodeURIComponent(exerciseId)}/draft`)),
  saveDraft: (id: string, exerciseId: string, code: string) =>
    request<Draft>(lessonPath(id, `/exercises/${encodeURIComponent(exerciseId)}/draft`), send("PUT", { code })),
  runTests: (id: string, exerciseId: string, code: string) =>
    request<RunResult>(lessonPath(id, `/exercises/${encodeURIComponent(exerciseId)}/run`), send("POST", { code })),
};

export interface Loaded<T> {
  data: T | undefined;
  error: Error | undefined;
  reload: () => void;
}

/** Load something once per change of `deps`; `reload()` fetches it again and keeps the old data meanwhile. */
export function useLoad<T>(load: () => Promise<T>, deps: unknown[]): Loaded<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<Error>();
  const [tick, setTick] = useState(0);
  const run = useCallback(load, deps);

  useEffect(() => {
    // Something else is being loaded now: don't show the previous one meanwhile.
    setData(undefined);
    setError(undefined);
  }, [run]);

  useEffect(() => {
    let live = true;
    run().then(
      (value) => live && (setData(value), setError(undefined)),
      (err: Error) => live && setError(err),
    );
    return () => {
      live = false;
    };
  }, [run, tick]);

  return { data, error, reload: useCallback(() => setTick((t) => t + 1), []) };
}

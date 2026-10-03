// The lesson kernel's WebSocket (spec §9.1, §9.2) and how its events become
// nbformat outputs. The protocol is documented in src/debrief/server/notebook.py.

import type { MimeBundle, Output } from "./api";

export type KernelEvent =
  | { type: "kernel"; session: string }
  | { type: "status"; state: "busy" | "idle" | string }
  | { type: "stream"; name: "stdout" | "stderr"; text: string }
  | {
      type: "display";
      data: MimeBundle;
      metadata: Record<string, unknown>;
      execution_count: number | null;
      display_id: string | null;
      update: boolean;
    }
  | { type: "error"; ename: string; evalue: string; traceback: string[] }
  | { type: "clear"; wait: boolean }
  | DoneEvent;

export interface DoneEvent {
  type: "done";
  status: "ok" | "error" | "aborted";
  execution_count: number | null;
}

interface Pending {
  onEvent: (event: KernelEvent) => void;
  resolve: (done: DoneEvent) => void;
}

/** One socket per open notebook. It connects on first use and reconnects after a drop. */
export class KernelSocket {
  private ws: WebSocket | null = null;
  private pending = new Map<string, Pending>();
  private outbox: string[] = [];
  private next = 0;

  constructor(private readonly lessonId: string) {}

  /** Run `code`; `onEvent` gets every event, and the promise resolves with the final `done`. */
  execute(code: string, onEvent: (event: KernelEvent) => void): Promise<DoneEvent> {
    const id = `r${++this.next}`;
    return new Promise((resolve) => {
      this.pending.set(id, { onEvent, resolve });
      this.send({ type: "execute", id, code });
    });
  }

  interrupt() {
    this.send({ type: "interrupt" });
  }

  close() {
    this.ws?.close();
    this.ws = null;
  }

  private send(message: object) {
    const text = JSON.stringify(message);
    const ws = this.ws ?? this.connect();
    if (ws.readyState === WebSocket.OPEN) ws.send(text);
    else this.outbox.push(text);
  }

  private connect(): WebSocket {
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${scheme}://${location.host}/api/lessons/${encodeURIComponent(this.lessonId)}/kernel/ws`);
    this.ws = ws;
    ws.onopen = () => {
      for (const text of this.outbox.splice(0)) ws.send(text);
    };
    ws.onmessage = (message) => {
      const event = JSON.parse(message.data) as KernelEvent & { id?: string };
      const pending = event.id ? this.pending.get(event.id) : undefined;
      if (!pending) return;
      pending.onEvent(event);
      if (event.type === "done") {
        this.pending.delete(event.id!);
        pending.resolve(event);
      }
    };
    ws.onclose = () => {
      if (this.ws === ws) this.ws = null;
      this.outbox = [];
      // Whatever was running can't report back any more.
      for (const [id, pending] of this.pending) {
        pending.onEvent({
          type: "error",
          ename: "ConnectionLost",
          evalue: "lost the connection to the debrief server; is `debrief serve` still running?",
          traceback: [],
        });
        pending.resolve({ type: "done", status: "aborted", execution_count: null });
        this.pending.delete(id);
      }
    };
    return ws;
  }
}

/** A cell's outputs while it runs. `display_id`s are kept for later updates and dropped when saving. */
export type LiveOutput = Output & { display_id?: string };

export interface OutputState {
  outputs: LiveOutput[];
  /** A `clear_output(wait=True)` is waiting for the next output. */
  clearPending: boolean;
}

/** Apply one event to a cell's outputs. Display updates go through `updateDisplay` instead. */
export function applyEvent(state: OutputState, event: KernelEvent): OutputState {
  if (event.type === "clear") return event.wait ? { ...state, clearPending: true } : { outputs: [], clearPending: false };
  if (event.type !== "stream" && event.type !== "display" && event.type !== "error") return state;
  if (event.type === "display" && event.update) return state;

  const outputs = state.clearPending ? [] : [...state.outputs];
  const last = outputs[outputs.length - 1];
  if (event.type === "stream") {
    if (last?.output_type === "stream" && last.name === event.name) {
      outputs[outputs.length - 1] = { ...last, text: joinText(last.text) + event.text };
    } else {
      outputs.push({ output_type: "stream", name: event.name, text: event.text });
    }
  } else if (event.type === "error") {
    outputs.push({ output_type: "error", ename: event.ename, evalue: event.evalue, traceback: event.traceback });
  } else {
    const base = { data: event.data, metadata: event.metadata, ...(event.display_id ? { display_id: event.display_id } : {}) };
    outputs.push(
      event.execution_count != null
        ? { output_type: "execute_result", execution_count: event.execution_count, ...base }
        : { output_type: "display_data", ...base },
    );
  }
  return { outputs, clearPending: false };
}

/** Replace the data of every output shown under `display_id` (IPython's `display(..., display_id=...).update`). */
export function updateDisplay(outputs: LiveOutput[], event: KernelEvent): LiveOutput[] {
  if (event.type !== "display" || !event.update || !event.display_id) return outputs;
  if (!outputs.some((o) => o.display_id === event.display_id)) return outputs;
  return outputs.map((o) =>
    o.display_id === event.display_id && o.output_type !== "stream" && o.output_type !== "error"
      ? { ...o, data: event.data, metadata: event.metadata }
      : o,
  );
}

/** Outputs as nbformat stores them. */
export function savedOutputs(outputs: LiveOutput[]): Output[] {
  return outputs.map(({ display_id: _, ...o }) => o as Output);
}

export const joinText = (text: string | string[]) => (Array.isArray(text) ? text.join("") : text);

/** Stream text as a terminal shows it: a carriage return rewrites the current line (progress bars). */
export function terminalText(text: string): string {
  const combined = text.replace(/\r\n/g, "\n");
  if (!combined.includes("\r")) return combined;
  return combined
    .split("\n")
    .map((line) => {
      // A trailing \r means the next write will replace this line; keep it showing until then.
      const parts = line.split("\r");
      const shown = parts.filter((p, i) => p !== "" || i === 0);
      return shown[shown.length - 1] ?? "";
    })
    .join("\n");
}

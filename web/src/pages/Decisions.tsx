// Decisions tab: one card per decision in decisions.md, each with a "Revisit
// decision" button that copies a prompt for Claude Code (spec §5.3).

import { RotateCcw } from "lucide-react";
import { useState } from "react";
import type { Decision, Decisions, Lesson, Loaded } from "../api";
import { Markdown } from "../components/Markdown";
import { Badge, Button, Callout, Status } from "../components/ui";

export function DecisionsTab({ lesson, decisions }: { lesson: Lesson; decisions: Loaded<Decisions | undefined> }) {
  if (!decisions.data) return <Status error={decisions.error} />;
  const { decisions: list, note } = decisions.data;
  const n = list.length;
  return (
    <div className="reading centred stack-4">
      {n > 0 ? (
        <p className="muted intro">
          {n === 1 ? "One choice" : `${n} choices`} the agent made while building this, with the options it rejected.
          Disagree with one? <strong className="ink">Revisit decision</strong> copies a prompt you can paste into
          Claude Code to challenge it.
        </p>
      ) : (
        <Callout title="No architectural decisions in this build.">
          {note && <Markdown text={note} lessonId={lesson.id} inline />}
        </Callout>
      )}
      {n > 0 && note && (
        <div className="muted">
          <Markdown text={note} lessonId={lesson.id} />
        </div>
      )}
      {list.map((d) => (
        <DecisionCard key={d.title} decision={d} lesson={lesson} />
      ))}
    </div>
  );
}

function DecisionCard({ decision: d, lesson }: { decision: Decision; lesson: Lesson }) {
  const md = (text: string) => <Markdown text={text} lessonId={lesson.id} inline />;
  const structured = d.options.length > 0;
  return (
    <article className="sy-card sy-decision">
      <div className="sy-overline">Decision</div>
      <h3 className="sy-h3">{d.title}</h3>
      {structured ? (
        <>
          {d.context && <p className="sy-decision-ctx">{md(d.context)}</p>}
          <ul className="sy-decision-opts">
            {d.options.map((o) => {
              const chosen = o.id === d.chosen;
              return (
                <li key={o.id} className={`sy-decision-opt${chosen ? " is-chosen" : ""}`}>
                  <span className="sy-decision-id">{o.id}</span>
                  <span>{md(o.label)}</span>
                  {chosen && <Badge tone="accent">Chosen</Badge>}
                </li>
              );
            })}
          </ul>
          {d.why && (
            <p className="sy-decision-why">
              <strong>Why: </strong>
              {md(d.why)}
            </p>
          )}
          {d.tradeoffs && (
            <p className="sy-decision-why">
              <strong>Trade-offs: </strong>
              {md(d.tradeoffs)}
            </p>
          )}
          {d.adr && (
            <p className="sy-decision-why">
              <strong>ADR: </strong>
              <span className="mono-sm">{d.adr}</span>
            </p>
          )}
        </>
      ) : (
        <div className="decision-body">
          <Markdown text={d.body} lessonId={lesson.id} />
        </div>
      )}
      <div className="sy-decision-foot">
        <RevisitButton prompt={revisitPrompt(d, lesson)} />
      </div>
    </article>
  );
}

function RevisitButton({ prompt }: { prompt: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(prompt);
      setState("copied");
    } catch {
      setState("failed");
    }
    setTimeout(() => setState("idle"), 2500);
  };
  return (
    <Button size="sm" icon={state === "copied" ? "✓" : <RotateCcw size={13} strokeWidth={1.5} />} onClick={copy}>
      {state === "copied" ? "Prompt copied" : state === "failed" ? "Couldn't copy" : "Revisit decision"}
    </Button>
  );
}

function revisitPrompt(d: Decision, lesson: Lesson): string {
  const lines = [
    `Reconsider the decision "${d.title}" in ${lesson.source.repo_path}.`,
    `It was made while building "${lesson.title}"${lesson.source.branch ? ` on branch ${lesson.source.branch}` : ""}.`,
    "",
  ];
  if (d.options.length > 0) {
    if (d.context) lines.push(`Context: ${d.context}`);
    lines.push("Options:", ...d.options.map((o) => `- ${o.id}: ${o.label}${o.id === d.chosen ? " (chosen)" : ""}`));
    if (d.why) lines.push(`Why it was chosen: ${d.why}`);
    if (d.tradeoffs) lines.push(`Trade-offs: ${d.tradeoffs}`);
  } else {
    lines.push(d.body);
  }
  lines.push(
    "",
    "Look at the current code and weigh the options again. Would you still make the same choice? " +
      "If not, explain what you would change, what it would cost, and wait for my go-ahead before changing anything.",
  );
  return lines.join("\n");
}

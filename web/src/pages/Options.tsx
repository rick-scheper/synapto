// Options tab of a decision lesson (spec §12, ADR-0008): the question, a
// criteria × options matrix and a card per option. A guided lesson shows the
// recommendation up front. An open lesson asks for the developer's choice and
// reasoning, points them to `/decide review`, and reveals the recommendation
// next to the review's verdict once that's done.

import { Terminal } from "lucide-react";
import { useState } from "react";
import { api, useLoad, type Candidate, type Criterion, type DecisionState, type Lesson, type Recommendation, type Review } from "../api";
import { Markdown } from "../components/Markdown";
import { Badge, Button, Callout, CopyButton, Status } from "../components/ui";
import { formatDate } from "../format";

const MAX_SCORE = 5;
const WEIGHT_LABEL: Record<number, string> = { 1: "Nice to have", 2: "Important", 3: "Decisive" };

export function OptionsTab({ lesson, onProgress }: { lesson: Lesson; onProgress: () => void }) {
  const state = useLoad(() => api.decision(lesson.id), [lesson.id]);
  if (!state.data) return <Status error={state.error} />;
  const d = state.data;
  const name = (id: string) => d.options.find((o) => o.id === id)?.name ?? id;
  const marks: Marks = {
    recommended: d.recommendation?.option,
    chosen: d.review?.verdict.final_option ?? d.choice?.option_id,
  };

  return (
    <div className="decision-page stack-5">
      <section className="stack-1">
        <div className="overline">The question</div>
        <h2 className="h2">{d.question}</h2>
        <p className="muted small">
          {d.mode === "guided"
            ? "Compare the options on the criteria that matter for this project, then see why the agent recommends the one it does."
            : "Compare the options on the criteria that matter for this project, then make the call yourself. The agent wrote down its own pick before you chose; you'll see it after the review."}
        </p>
      </section>

      {d.review && <ReviewPanel review={d.review} lessonId={lesson.id} name={name} />}
      {d.recommendation && <RecommendationCard rec={d.recommendation} lessonId={lesson.id} name={name} />}

      <Matrix criteria={d.criteria} options={d.options} marks={marks} />

      <div className="option-grid">
        {d.options.map((o) => (
          <OptionCard key={o.id} option={o} lessonId={lesson.id} marks={marks} />
        ))}
      </div>

      {d.mode === "open" && !d.review && (
        <ChoicePanel
          lessonId={lesson.id}
          state={d}
          onSaved={() => {
            state.reload();
            onProgress();
          }}
        />
      )}
    </div>
  );
}

interface Marks {
  recommended?: string;
  chosen?: string;
}

function OptionBadges({ id, marks }: { id: string; marks: Marks }) {
  return (
    <>
      {marks.chosen === id && <Badge tone="accent">Your choice</Badge>}
      {marks.recommended === id && <Badge tone="success">Recommended</Badge>}
    </>
  );
}

function Matrix({ criteria, options, marks }: { criteria: Criterion[]; options: Candidate[]; marks: Marks }) {
  const highlight = (id: string) => (id === marks.chosen || id === marks.recommended ? " is-marked" : "");
  return (
    <div className="matrix-wrap">
      <table className="matrix">
        <thead>
          <tr>
            <th scope="col">Criterion</th>
            {options.map((o) => (
              <th key={o.id} scope="col" className={highlight(o.id)}>
                {o.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {criteria.map((c) => (
            <tr key={c.id}>
              <th scope="row">
                <span className="matrix-criterion">{c.name}</span>
                <span className="caption muted">
                  {WEIGHT_LABEL[c.weight]} · {c.description}
                </span>
              </th>
              {options.map((o) => (
                <td key={o.id} className={highlight(o.id)}>
                  <Score value={o.scores[c.id]} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Score({ value }: { value: number }) {
  return (
    <span className="score" role="img" aria-label={`${value} out of ${MAX_SCORE}`}>
      {Array.from({ length: MAX_SCORE }, (_, i) => (
        <span key={i} className={`score-pip${i < value ? " is-on" : ""}`} />
      ))}
    </span>
  );
}

function OptionCard({ option: o, lessonId, marks }: { option: Candidate; lessonId: string; marks: Marks }) {
  const md = (text: string) => <Markdown text={text} lessonId={lessonId} inline />;
  return (
    <article className={`sy-card option-card${marks.chosen === o.id ? " is-chosen" : ""}`}>
      <div className="row-2">
        <h3 className="sy-h3 grow">{o.name}</h3>
        <OptionBadges id={o.id} marks={marks} />
      </div>
      <p className="small muted">{md(o.summary)}</p>
      <div className="option-lists">
        <div>
          <div className="overline">Strengths</div>
          <ul className="small">
            {o.strengths.map((s) => (
              <li key={s}>{md(s)}</li>
            ))}
          </ul>
        </div>
        <div>
          <div className="overline">Weaknesses</div>
          <ul className="small">
            {o.weaknesses.map((s) => (
              <li key={s}>{md(s)}</li>
            ))}
          </ul>
        </div>
      </div>
      <p className="small">
        <strong>Fits when: </strong>
        {md(o.fits_when)}
      </p>
      {o.links.length > 0 && (
        <ul className="option-links small">
          {o.links.map((l) => (
            <li key={l.url}>
              <a href={l.url} target="_blank" rel="noreferrer">
                {l.title}
              </a>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

function RecommendationCard({ rec, lessonId, name }: { rec: Recommendation; lessonId: string; name: (id: string) => string }) {
  const md = (text: string) => <Markdown text={text} lessonId={lessonId} inline />;
  return (
    <article className="sy-card sy-decision recommendation">
      <div className="sy-overline">The agent's recommendation</div>
      <h3 className="sy-h3">{name(rec.option)}</h3>
      <p className="sy-decision-why">
        <strong>Why: </strong>
        {md(rec.why)}
      </p>
      <p className="sy-decision-why">
        <strong>Trade-offs: </strong>
        {md(rec.trade_offs)}
      </p>
      <p className="sy-decision-why">
        <strong>Would change if: </strong>
        {md(rec.would_change_if)}
      </p>
    </article>
  );
}

function ReviewPanel({ review, lessonId, name }: { review: Review; lessonId: string; name: (id: string) => string }) {
  const { verdict } = review;
  return (
    <section className="panel stack-4" aria-label="Review">
      <div className="row-2">
        <div className="stack-0 grow">
          <div className="overline">Review · {formatDate(review.reviewed_at)}</div>
          <h3 className="h-card">You settled on {name(verdict.final_option)}</h3>
        </div>
        <Badge tone={review.agrees ? "success" : "neutral"}>
          {review.agrees ? "Same as the agent's pick" : "Different from the agent's pick"}
        </Badge>
      </div>
      <ol className="challenges">
        {verdict.challenges.map((c) => (
          <li key={c.question}>
            <div className="strong">{c.question}</div>
            <div className="muted small">{c.response}</div>
          </li>
        ))}
      </ol>
      <div className="stack-1">
        <div className="overline">The agent's opinion</div>
        <Markdown text={verdict.opinion} lessonId={lessonId} />
      </div>
      {review.adr_path && (
        <p className="small muted">
          Recorded in the project as <span className="mono-sm">{review.adr_path}</span>
        </p>
      )}
    </section>
  );
}

function ChoicePanel({ lessonId, state, onSaved }: { lessonId: string; state: DecisionState; onSaved: () => void }) {
  const [optionId, setOptionId] = useState(state.choice?.option_id ?? "");
  const [reasoning, setReasoning] = useState(state.choice?.reasoning ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error>();
  const saved = state.choice;
  const changed = !saved || saved.option_id !== optionId || saved.reasoning !== reasoning.trim();

  const save = async () => {
    setBusy(true);
    setError(undefined);
    try {
      await api.saveChoice(lessonId, optionId, reasoning);
      onSaved();
    } catch (err) {
      setError(err as Error);
    } finally {
      setBusy(false);
    }
  };

  const command = `/decide review ${lessonId}`;
  return (
    <section className="panel stack-4" aria-label="Your decision">
      <div className="stack-1">
        <div className="overline">Your decision</div>
        <p className="small muted">
          There is no wrong answer. Pick the option you would build on, and write down why: the review challenges that
          reasoning, not the pick.
        </p>
      </div>
      <div className="sy-decision-opts" role="radiogroup" aria-label="Options">
        {state.options.map((o) => (
          <button
            key={o.id}
            type="button"
            role="radio"
            aria-checked={optionId === o.id}
            className={`sy-decision-opt choice-opt${optionId === o.id ? " is-chosen" : ""}`}
            onClick={() => setOptionId(o.id)}
          >
            <span className="sy-decision-id">{optionId === o.id ? "●" : "○"}</span>
            <span>{o.name}</span>
          </button>
        ))}
      </div>
      <label className="sy-field">
        <span className="sy-field-label">Why this one?</span>
        <textarea
          className="sy-input textarea"
          value={reasoning}
          onChange={(e) => setReasoning(e.target.value)}
          placeholder="Which criteria tipped it, and what you're willing to give up."
          rows={5}
        />
      </label>
      <div className="row-2">
        <Button variant="primary" onClick={save} disabled={busy || !optionId || !reasoning.trim() || !changed}>
          {saved ? "Update decision" : "Save decision"}
        </Button>
        {saved && !changed && <span className="caption muted">Saved {formatDate(saved.decided_at)}</span>}
        {error && <span className="caption danger">{error.message}</span>}
      </div>
      {saved && (
        <Callout
          title="Next: have the agent test your decision."
          action={
            <CopyButton text={command} icon={<Terminal size={13} strokeWidth={1.5} />}>
              Copy command
            </CopyButton>
          }
        >
          Run <code className="md-code">{command}</code> in Claude Code. It asks you a few questions about your
          reasoning, then shows its own pick here. You can change your decision until then.
        </Callout>
      )}
    </section>
  );
}

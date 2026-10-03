// Quiz tab (spec §12): one question at a time, the explanation after each
// answer and a score at the end. Answers are recorded through the API; the
// latest answer to each question is what counts toward progress.

import { useState } from "react";
import { api, useLoad, type Answer, type QuizQuestion } from "../api";
import { Markdown } from "../components/Markdown";
import { Badge, Button, ProgressRing, QuizOption, Status, type QuizOptionState } from "../components/ui";

type View = number | "score";

export function QuizTab({
  lessonId,
  answers,
  onAnswered,
}: {
  lessonId: string;
  answers: Record<string, Answer>;
  onAnswered: () => void;
}) {
  const quiz = useLoad(() => api.quiz(lessonId), [lessonId]);
  // Answers given in this tab, shown at once rather than after the lesson reloads.
  const [local, setLocal] = useState<Record<string, Answer>>({});
  // A retake starts from a clean sheet: earlier answers stay on record but aren't shown.
  const [retake, setRetake] = useState(false);
  const [view, setView] = useState<View>();

  if (!quiz.data) return <Status error={quiz.error} />;
  const questions = quiz.data.questions;
  const answered = retake ? local : { ...answers, ...local };
  const firstOpen = questions.findIndex((q) => !answered[q.id]);
  const current: View = view ?? (firstOpen === -1 ? "score" : firstOpen);
  const nCorrect = questions.filter((q) => answered[q.id]?.correct).length;
  const nAnswered = questions.filter((q) => answered[q.id]).length;

  const record = (index: number, answer: Answer) => {
    // Stay on this question to show its explanation, rather than moving on to the next open one.
    setView(index);
    setLocal((prev) => ({ ...prev, [questions[index].id]: answer }));
    onAnswered();
  };
  const next = (from: number) => {
    const open = questions.findIndex((q, i) => i > from && !answered[q.id]);
    const anyOpen = questions.findIndex((q) => !answered[q.id]);
    setView(open !== -1 ? open : anyOpen !== -1 ? anyOpen : "score");
  };

  return (
    <div className="with-sidebar">
      <aside className="sidebar">
        <nav className="question-list" aria-label="Questions">
          <h2 className="overline ink">Questions</h2>
          {questions.map((q, i) => {
            const a = answered[q.id];
            return (
              <button
                key={q.id}
                type="button"
                className={`question-row${current === i ? " is-current" : ""}${a ? " is-done" : ""}`}
                onClick={() => setView(i)}
              >
                <span className={`question-mark ${a ? (a.correct ? "ok" : "bad") : ""}`} aria-hidden>
                  {a ? (a.correct ? "✓" : "✕") : current === i ? "•" : ""}
                </span>
                <span className="grow">
                  Question {i + 1}
                  {a && <span className="visually-hidden">{a.correct ? ", correct" : ", not quite"}</span>}
                </span>
                {q.concept && <span className="caption muted truncate">{q.concept}</span>}
              </button>
            );
          })}
          <div className="score-line">
            Score so far{" "}
            <span className="ink strong">
              {nCorrect} of {nAnswered}
            </span>
          </div>
        </nav>
      </aside>
      <div className="reading">
        {current === "score" ? (
          <Score
            questions={questions}
            answered={answered}
            lessonId={lessonId}
            onReview={() => setView(0)}
            onRetake={() => (setRetake(true), setLocal({}), setView(0))}
          />
        ) : (
          <Question
            key={`${questions[current].id}-${retake}`}
            lessonId={lessonId}
            question={questions[current]}
            number={current + 1}
            total={questions.length}
            nAnswered={nAnswered}
            answer={answered[questions[current].id]}
            onAnswer={(a) => record(current, a)}
            onNext={() => next(current)}
            last={nAnswered === questions.length}
          />
        )}
      </div>
    </div>
  );
}

function Question({
  lessonId,
  question: q,
  number,
  total,
  nAnswered,
  answer,
  onAnswer,
  onNext,
  last,
}: {
  lessonId: string;
  question: QuizQuestion;
  number: number;
  total: number;
  nAnswered: number;
  answer: Answer | undefined;
  onAnswer: (a: Answer) => void;
  onNext: () => void;
  last: boolean;
}) {
  const [picked, setPicked] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error>();
  const md = (text: string) => <Markdown text={text} lessonId={lessonId} inline />;

  const check = async () => {
    if (!picked) return;
    setBusy(true);
    try {
      const result = await api.answer(lessonId, q.id, picked);
      onAnswer({ option_id: picked, correct: result.correct });
      setError(undefined);
    } catch (err) {
      setError(err as Error);
    } finally {
      setBusy(false);
    }
  };

  const stateOf = (id: string): QuizOptionState => {
    if (answer) return id === q.correct ? "correct" : id === answer.option_id ? "wrong" : "idle";
    return id === picked ? "selected" : "idle";
  };

  return (
    <section className="stack-5 question">
      <div className="question-progress">
        <span className="overline">
          Question {number} of {total}
        </span>
        <span className="bar" aria-hidden>
          <span style={{ width: `${(nAnswered / total) * 100}%` }} />
        </span>
      </div>
      <h2 className="h2 question-prompt">{md(q.prompt)}</h2>
      {!answer && <p className="muted small">Pick one, then check your answer.</p>}
      <div className="stack-2">
        {q.options.map((o) => (
          <QuizOption
            key={o.id}
            optionId={o.id}
            state={stateOf(o.id)}
            disabled={!!answer || busy}
            onClick={() => setPicked(o.id)}
          >
            {md(o.text)}
          </QuizOption>
        ))}
      </div>
      {error && <Status error={error} />}
      {answer && (
        <section className="panel stack-2" aria-live="polite">
          <div className="row-2">
            <Badge tone={answer.correct ? "success" : "danger"}>{answer.correct ? "Correct" : "Not quite"}</Badge>
            {q.concept && <span className="overline">{q.concept}</span>}
          </div>
          <Markdown text={q.explanation} lessonId={lessonId} />
          {q.source_ref && <span className="mono-sm muted">{q.source_ref}</span>}
        </section>
      )}
      <div className="actions">
        {answer ? (
          <Button variant="primary" onClick={onNext}>
            {last ? "See your score" : "Next question"}
          </Button>
        ) : (
          <Button variant="primary" disabled={!picked || busy} onClick={check}>
            Check answer
          </Button>
        )}
      </div>
    </section>
  );
}

function Score({
  questions,
  answered,
  lessonId,
  onReview,
  onRetake,
}: {
  questions: QuizQuestion[];
  answered: Record<string, Answer>;
  lessonId: string;
  onReview: () => void;
  onRetake: () => void;
}) {
  const correct = questions.filter((q) => answered[q.id]?.correct).length;
  return (
    <section className="stack-5">
      <div className="row-4">
        <ProgressRing value={correct / questions.length} size={56} stroke={5} />
        <div className="stack-1">
          <div className="overline">Quiz complete</div>
          <h2 className="h2">
            {correct} of {questions.length} right
          </h2>
        </div>
      </div>
      <ol className="score-list">
        {questions.map((q) => {
          const ok = answered[q.id]?.correct;
          return (
            <li key={q.id} className={ok ? "ok" : "bad"}>
              <span className="question-mark" aria-hidden>
                {ok ? "✓" : "✕"}
              </span>
              <span className="grow">
                <Markdown text={q.prompt} lessonId={lessonId} inline />
              </span>
              <span className="caption strong">{ok ? "Correct" : "Not quite"}</span>
            </li>
          );
        })}
      </ol>
      <div className="actions">
        <Button onClick={onReview}>Review answers</Button>
        <Button variant="primary" onClick={onRetake}>
          Retake quiz
        </Button>
      </div>
    </section>
  );
}

// Library (spec §12): lesson cards grouped by repo, concept filters, progress
// rings and staleness badges.

import { ArrowRight } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { api, useLoad, type LessonSummary } from "../api";
import { Badge, ProgressRing, Status } from "../components/ui";
import { difficultyLabel, formatDate, plural, repoName, shortCommit } from "../format";

const MAX_CHIPS = 6;
const MAX_CARD_CONCEPTS = 4;

export function Library() {
  const [params, setParams] = useSearchParams();
  const concept = params.get("concept") ?? undefined;
  const query = (params.get("q") ?? "").trim().toLowerCase();

  const lessons = useLoad(() => api.lessons(concept), [concept]);
  const totals = useLoad(api.progress, []);

  const pickConcept = (name?: string) => {
    const next = new URLSearchParams(params);
    if (name) next.set("concept", name);
    else next.delete("concept");
    setParams(next, { replace: true });
  };

  if (!lessons.data || !totals.data) return <main className="page"><Status error={lessons.error ?? totals.error} /></main>;
  const t = totals.data;
  if (t.lessons === 0) return <EmptyLibrary />;

  const shown = lessons.data.filter(
    (l) =>
      !query ||
      l.title.toLowerCase().includes(query) ||
      l.summary.toLowerCase().includes(query) ||
      l.concepts.some((c) => c.toLowerCase().includes(query)),
  );
  const chips = t.concepts.slice(0, MAX_CHIPS).map((c) => c.name);
  if (concept && !chips.includes(concept)) chips.push(concept);
  const repos = new Set(lessons.data.map((l) => l.repo_path)).size;
  const resume = continueWith(lessons.data);

  return (
    <main className="page library">
      <section className="library-head">
        <div className="stack-1">
          <div className="overline">Library</div>
          <h1 className="h1">Lessons</h1>
          <p className="muted small">
            {[
              `${plural(t.lessons, "lesson")} across ${plural(repos, "repo")}`,
              t.in_progress && `${t.in_progress} in progress`,
              t.stale && `${t.stale} stale`,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <div className="chips" role="group" aria-label="Filter by concept">
          <span className="muted small">Concept</span>
          <Chip on={!concept} onClick={() => pickConcept()}>
            All
          </Chip>
          {chips.map((name) => (
            <Chip key={name} on={concept === name} onClick={() => pickConcept(name)}>
              {name}
            </Chip>
          ))}
        </div>
      </section>

      {resume && !concept && !query && <ContinueBanner lesson={resume} />}

      {shown.length === 0 && <p className="muted">No lessons match. Clear the search or pick another concept.</p>}

      {groupByRepo(shown).map(([repoPath, group]) => (
        <section key={repoPath} className="repo-group">
          <div className="repo-head">
            <h2 className="overline ink">{repoName(repoPath)}</h2>
            <span className="mono-sm muted">{repoPath}</span>
            <span className="grow" />
            <span className="caption muted">{plural(group.length, "lesson")}</span>
          </div>
          <div className="card-grid">
            {group.map((lesson) => (
              <LessonCard key={lesson.id} lesson={lesson} />
            ))}
          </div>
        </section>
      ))}
    </main>
  );
}

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: string }) {
  return (
    <button type="button" className={`chip${on ? " is-on" : ""}`} aria-pressed={on} onClick={onClick}>
      {children}
    </button>
  );
}

function LessonCard({ lesson }: { lesson: LessonSummary }) {
  const extra = lesson.concepts.length - MAX_CARD_CONCEPTS;
  const foot = [lesson.branch, shortCommit(lesson.head_commit)].filter(Boolean).join(" · ");
  return (
    <Link to={`/lessons/${lesson.id}`} className="sy-card sy-lesson">
      <div className="sy-lesson-top">
        <div>
          <div className="sy-overline">
            {formatDate(lesson.created_at)} · {difficultyLabel(lesson.difficulty)}
          </div>
          <h3 className="sy-h3 sy-lesson-title">{lesson.title}</h3>
        </div>
        <ProgressRing value={lesson.progress.value} />
      </div>
      <p className="sy-lesson-summary">{lesson.summary}</p>
      <div className="sy-lesson-chips">
        {lesson.concepts.slice(0, MAX_CARD_CONCEPTS).map((c) => (
          <Badge key={c} tone="accent">
            {c}
          </Badge>
        ))}
        {extra > 0 && <Badge>+{extra}</Badge>}
        {lesson.staleness.stale && <Badge tone="warning">Stale</Badge>}
      </div>
      {foot && <div className="sy-lesson-repo">{foot}</div>}
    </Link>
  );
}

function ContinueBanner({ lesson }: { lesson: LessonSummary }) {
  const { quiz, exercises } = lesson.progress;
  const quizOpen = quiz.answered < quiz.total;
  return (
    <section className="continue panel" aria-label="Continue">
      <ProgressRing value={lesson.progress.value} size={56} stroke={5} />
      <div className="continue-text">
        <div className="overline">Continue where you left off</div>
        <div className="h-card">{lesson.title}</div>
        <div className="muted small">
          {quizOpen && "Next: Quiz · "}
          {quiz.answered} of {quiz.total} answered · Rebuild {exercises.passed} of {exercises.total} passed
        </div>
      </div>
      <Link to={`/lessons/${lesson.id}${quizOpen ? "/quiz" : ""}`} className="sy-btn sy-btn-primary">
        Continue lesson <ArrowRight size={14} strokeWidth={2} aria-hidden />
      </Link>
    </section>
  );
}

function EmptyLibrary() {
  return (
    <main className="page empty">
      <span className="logo-tile">
        <img src="/synapto-logo-lockup.png" alt="Synapto" />
      </span>
      <h1 className="h2">No lessons yet</h1>
      <p className="muted">
        After the agent builds something, run <code className="md-code">/debrief</code> in Claude Code. The lesson
        shows up here once it's published.
      </p>
    </main>
  );
}

/** The most recently opened lesson that isn't finished. */
function continueWith(lessons: LessonSummary[]): LessonSummary | undefined {
  return lessons
    .filter((l) => l.opened_at && l.progress.value < 1)
    .sort((a, b) => b.opened_at!.localeCompare(a.opened_at!))[0];
}

function groupByRepo(lessons: LessonSummary[]): [string, LessonSummary[]][] {
  const groups = new Map<string, LessonSummary[]>();
  for (const lesson of lessons) groups.set(lesson.repo_path, [...(groups.get(lesson.repo_path) ?? []), lesson]);
  return [...groups];
}

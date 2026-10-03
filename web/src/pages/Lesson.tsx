// A lesson (spec §12): header, staleness banner and the tabs.

import { ArrowLeft } from "lucide-react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { api, useLoad, type LessonDetail } from "../api";
import { Callout, ProgressRing, Status, Tabs, type TabItem } from "../components/ui";
import { difficultyLabel, formatDate, plural, repoName, shortCommit } from "../format";
import { DecisionsTab } from "./Decisions";
import { ExplainTab } from "./Explain";
import { NotebookTab } from "./Notebook";
import { QuizTab } from "./Quiz";
import { RebuildTab } from "./Rebuild";

const TABS = ["explain", "decisions", "notebook", "quiz", "rebuild"] as const;
type Tab = (typeof TABS)[number];

export function LessonPage() {
  const { id = "", tab = "explain" } = useParams();
  const navigate = useNavigate();
  const detail = useLoad(() => api.lesson(id), [id]);
  const decisions = useLoad(() => api.decisions(id), [id]);

  if (!TABS.includes(tab as Tab)) return <Navigate to={`/lessons/${id}`} replace />;
  if (!detail.data) {
    return (
      <main className="page">
        <BackLink />
        <Status error={detail.error} />
      </main>
    );
  }
  const { lesson, progress } = detail.data;

  const items: TabItem[] = [
    { id: "explain", label: "Explain" },
    { id: "decisions", label: "Decisions", count: decisions.data?.decisions.length || undefined },
    { id: "notebook", label: "Notebook" },
    { id: "quiz", label: "Quiz", count: progress.quiz.total - progress.quiz.answered || undefined },
    { id: "rebuild", label: "Rebuild", count: progress.exercises.total - progress.exercises.passed || undefined },
  ];

  return (
    <main className="page lesson">
      <BackLink />
      <LessonHeader detail={detail.data} />
      <StaleBanner detail={detail.data} />
      <Tabs items={items} value={tab} onChange={(t) => navigate(`/lessons/${id}${t === "explain" ? "" : `/${t}`}`)} />
      <div className="tab-body">
        {tab === "explain" && <ExplainTab lessonId={id} />}
        {tab === "decisions" && <DecisionsTab lesson={lesson} decisions={decisions} />}
        {tab === "notebook" && <NotebookTab lesson={lesson} />}
        {tab === "quiz" && <QuizTab lessonId={id} answers={detail.data.answers} onAnswered={detail.reload} />}
        {tab === "rebuild" && <RebuildTab lessonId={id} onProgress={detail.reload} />}
      </div>
    </main>
  );
}

function BackLink() {
  return (
    <Link to="/" className="back-link">
      <ArrowLeft size={14} strokeWidth={1.5} aria-hidden />
      All lessons
    </Link>
  );
}

function LessonHeader({ detail: { lesson, progress } }: { detail: LessonDetail }) {
  const { source } = lesson;
  const commits = [shortCommit(source.base_commit), shortCommit(source.head_commit)].filter(Boolean).join(" → ");
  const sourceLine = [
    repoName(source.repo_path),
    source.branch,
    commits,
    source.includes_uncommitted && "uncommitted changes",
    plural(source.files.length, "file"),
  ]
    .filter(Boolean)
    .join(" · ");
  const pct = Math.round(progress.value * 100);
  return (
    <section className="lesson-head">
      <div className="lesson-head-main">
        <div className="overline">
          Lesson · {difficultyLabel(lesson.difficulty)} · {formatDate(lesson.created_at)}
        </div>
        <h1 className="h1">{lesson.title}</h1>
        <p className="lead">{lesson.summary}</p>
        <div className="mono-sm muted" title={source.repo_path}>
          {sourceLine}
        </div>
      </div>
      <div className="lesson-progress">
        <ProgressRing value={progress.value} size={48} />
        <div className="stack-0">
          <span className="label">{pct >= 100 ? "Complete" : `${pct}% complete`}</span>
          <span className="caption muted">
            Quiz {progress.quiz.answered}/{progress.quiz.total} · Rebuild {progress.exercises.passed}/
            {progress.exercises.total}
          </span>
        </div>
      </div>
    </section>
  );
}

function StaleBanner({ detail: { lesson, staleness } }: { detail: LessonDetail }) {
  if (!staleness.stale) return null;
  if (staleness.repo_missing) {
    return (
      <Callout tone="warning" title="The project folder for this lesson is gone.">
        <span className="mono-sm">{lesson.source.repo_path}</span> no longer exists, so the lesson can't be compared
        with the current code.
      </Callout>
    );
  }
  const n = staleness.changed.length;
  return (
    <Callout
      tone="warning"
      title={`The code has changed since this lesson was made — ${plural(n, "file differs", "files differ")}.`}
    >
      <ul className="changed-files">
        {staleness.changed.map((f) => (
          <li key={f.path}>
            <span className="mono-sm">{f.path}</span> <span className="muted">{f.change}</span>
          </li>
        ))}
      </ul>
    </Callout>
  );
}

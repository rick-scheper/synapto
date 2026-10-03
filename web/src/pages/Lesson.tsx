// A lesson (spec §12): header, staleness banner and a tab for each of its parts.

import { ArrowLeft, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { api, completable, PARTS, useLoad, type LessonDetail, type Part } from "../api";
import { HasNotebook } from "../components/Markdown";
import { Button, Callout, ProgressRing, Status, Tabs, type TabItem } from "../components/ui";
import { difficultyLabel, formatDate, plural, repoName, shortCommit } from "../format";
import { DecisionsTab } from "./Decisions";
import { ExplainTab } from "./Explain";
import { NotebookTab } from "./Notebook";
import { QuizTab } from "./Quiz";
import { RebuildTab } from "./Rebuild";

export function LessonPage() {
  const { id = "", tab: tabParam } = useParams();
  const navigate = useNavigate();
  const detail = useLoad(() => api.lesson(id), [id]);
  const parts = detail.data?.lesson.parts;
  const hasDecisions = parts?.includes("decisions") ?? false;
  const decisions = useLoad(
    () => (hasDecisions ? api.decisions(id) : Promise.resolve(undefined)),
    [id, hasDecisions],
  );

  if (tabParam !== undefined && !PARTS.includes(tabParam as Part)) return <Navigate to={`/lessons/${id}`} replace />;
  if (!detail.data) {
    return (
      <main className="page">
        <BackLink />
        <Status error={detail.error} />
      </main>
    );
  }
  const { lesson, progress } = detail.data;
  // Without a tab in the URL, the lesson opens on its first part.
  const shown = PARTS.filter((p) => lesson.parts.includes(p));
  const tab = (tabParam ?? shown[0]) as Part;
  if (!shown.includes(tab)) return <Navigate to={`/lessons/${id}`} replace />;

  const all: Record<Part, TabItem> = {
    explain: { id: "explain", label: "Explain" },
    decisions: { id: "decisions", label: "Decisions", count: decisions.data?.decisions.length || undefined },
    notebook: { id: "notebook", label: "Notebook" },
    quiz: { id: "quiz", label: "Quiz", count: progress.quiz.total - progress.quiz.answered || undefined },
    rebuild: { id: "rebuild", label: "Rebuild", count: progress.exercises.total - progress.exercises.passed || undefined },
  };
  const items = shown.map((p) => all[p]);

  return (
    <main className="page lesson">
      <BackLink />
      <LessonHeader detail={detail.data} />
      <StaleBanner detail={detail.data} />
      <Tabs items={items} value={tab} onChange={(t) => navigate(`/lessons/${id}${t === shown[0] ? "" : `/${t}`}`)} />
      <HasNotebook.Provider value={shown.includes("notebook")}>
        <div className="tab-body">
          {tab === "explain" && <ExplainTab lessonId={id} />}
          {tab === "decisions" && <DecisionsTab lesson={lesson} decisions={decisions} />}
          {tab === "notebook" && <NotebookTab lesson={lesson} />}
          {tab === "quiz" && <QuizTab lessonId={id} answers={detail.data.answers} onAnswered={detail.reload} />}
          {tab === "rebuild" && <RebuildTab lessonId={id} onProgress={detail.reload} />}
        </div>
      </HasNotebook.Provider>
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
  const counts = [
    lesson.parts.includes("quiz") && `Quiz ${progress.quiz.answered}/${progress.quiz.total}`,
    lesson.parts.includes("rebuild") && `Rebuild ${progress.exercises.passed}/${progress.exercises.total}`,
  ]
    .filter(Boolean)
    .join(" · ");
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
      <div className="lesson-side">
        {completable(progress) && (
          <div className="lesson-progress">
            <ProgressRing value={progress.value} size={48} />
            <div className="stack-0">
              <span className="label">{pct >= 100 ? "Complete" : `${pct}% complete`}</span>
              <span className="caption muted">{counts}</span>
            </div>
          </div>
        )}
        <DeleteButton lessonId={lesson.id} title={lesson.title} />
      </div>
    </section>
  );
}

function DeleteButton({ lessonId, title }: { lessonId: string; title: string }) {
  const navigate = useNavigate();
  const [error, setError] = useState<Error>();
  const [busy, setBusy] = useState(false);

  const remove = async () => {
    if (!window.confirm(`Delete "${title}" and all your progress in it? This can't be undone.`)) return;
    setBusy(true);
    try {
      await api.deleteLesson(lessonId);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err as Error);
      setBusy(false);
    }
  };

  return (
    <div className="stack-0 lesson-delete">
      <Button variant="ghost" size="sm" icon={<Trash2 size={14} strokeWidth={1.5} />} onClick={remove} disabled={busy}>
        Delete lesson
      </Button>
      {error && <span className="caption danger">{error.message}</span>}
    </div>
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

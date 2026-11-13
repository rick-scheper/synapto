// A lesson (spec §12): a flight-plan header whose route has a waypoint for each of
// the lesson's parts, status lights for staleness and completion, and the open part.

import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CircleHelp,
  Hammer,
  ListChecks,
  NotebookPen,
  Plane,
  Scale,
  Trash2,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { api, completable, PARTS, useLoad, type Decisions, type LessonDetail, type Part } from "../api";
import { HasNotebook } from "../components/Markdown";
import { Button, ProgressRing, Status } from "../components/ui";
import { difficultyLabel, formatDate, plural, repoName, shortCommit } from "../format";
import { DecisionsTab } from "./Decisions";
import { ExplainTab } from "./Explain";
import { NotebookTab } from "./Notebook";
import { OptionsTab } from "./Options";
import { QuizTab } from "./Quiz";
import { RebuildTab } from "./Rebuild";

const PART: Record<Part, { label: string; code: string; icon: LucideIcon }> = {
  explain: { label: "Explain", code: "EXPL", icon: BookOpen },
  decisions: { label: "Decisions", code: "DCSN", icon: ListChecks },
  options: { label: "Options", code: "OPTS", icon: Scale },
  notebook: { label: "Notebook", code: "NTBK", icon: NotebookPen },
  quiz: { label: "Quiz", code: "QUIZ", icon: CircleHelp },
  rebuild: { label: "Rebuild", code: "RBLD", icon: Hammer },
};

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
  const { lesson } = detail.data;
  // Without a part in the URL, the lesson opens on its first part.
  const shown = PARTS.filter((p) => lesson.parts.includes(p));
  const tab = (tabParam ?? shown[0]) as Part;
  if (!shown.includes(tab)) return <Navigate to={`/lessons/${id}`} replace />;

  const go = (part: Part) => navigate(`/lessons/${id}${part === shown[0] ? "" : `/${part}`}`);
  const route: RouteProps = { parts: shown, current: tab, detail: detail.data, decisions: decisions.data, go };
  const next = shown[shown.indexOf(tab) + 1];

  return (
    <main className="lesson">
      <FlightPlan route={route} />
      <div className="page lesson-body">
        <HasNotebook.Provider value={shown.includes("notebook")}>
          {tab === "explain" && <ExplainTab lessonId={id} />}
          {tab === "decisions" && <DecisionsTab lesson={lesson} decisions={decisions} />}
          {tab === "options" && <OptionsTab lesson={lesson} onProgress={detail.reload} />}
          {tab === "notebook" && <NotebookTab lesson={lesson} />}
          {tab === "quiz" && <QuizTab lessonId={id} answers={detail.data.answers} onAnswered={detail.reload} />}
          {tab === "rebuild" && <RebuildTab lessonId={id} onProgress={detail.reload} />}
        </HasNotebook.Provider>
        {next && (
          <button
            type="button"
            className="next-part"
            onClick={() => {
              go(next);
              window.scrollTo({ top: 0 });
            }}
          >
            <span className="overline">Next</span>
            <span className="h-card">
              {PART[next].label} <ArrowRight size={18} strokeWidth={1.5} aria-hidden />
            </span>
          </button>
        )}
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

interface RouteProps {
  parts: Part[];
  current: Part;
  detail: LessonDetail;
  decisions: Decisions | undefined;
  go: (part: Part) => void;
}

/** The lesson header. Once it scrolls away, a slim strip with the route takes its place. */
function FlightPlan({ route }: { route: RouteProps }) {
  const { lesson, progress } = route.detail;
  const header = useRef<HTMLElement>(null);
  const [scrolledPast, setScrolledPast] = useState(false);

  useEffect(() => {
    const el = header.current;
    if (!el) return;
    const top = getComputedStyle(document.documentElement).getPropertyValue("--header-height").trim() || "56px";
    const io = new IntersectionObserver(([e]) => setScrolledPast(!e.isIntersecting), { rootMargin: `-${top} 0px 0px 0px` });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const kind = lesson.kind === "decision" ? `${lesson.mode === "open" ? "Open" : "Guided"} decision` : "Lesson";
  return (
    <>
      <header ref={header} className="flight-plan">
        <div className="flight-plan-inner">
          <div className="flight-plan-row">
            <BackLink />
            <div className="grow" />
            <StatusLights detail={route.detail} />
          </div>
          <div className="flight-plan-title">
            <div className="lesson-title">
              <div className="overline">
                {kind} · {difficultyLabel(lesson.difficulty)} · {formatDate(lesson.created_at)}
              </div>
              <h1 className="h1">{lesson.title}</h1>
              <p className="lead">{lesson.summary}</p>
            </div>
            {completable(progress) && <ProgressRing value={progress.value} size={72} stroke={6} />}
          </div>
          <PartRoute {...route} />
          <div className="flight-plan-row">
            <SourceLine detail={route.detail} />
            <div className="grow" />
            <DeleteButton lessonId={lesson.id} title={lesson.title} />
          </div>
          <ChangedFiles detail={route.detail} />
        </div>
      </header>
      <div className={`route-strip${scrolledPast ? " is-shown" : ""}`} inert={!scrolledPast}>
        <span className="route-strip-title">{lesson.title}</span>
        <PartRoute {...route} mini />
        {completable(progress) && <span className="mono-sm">{Math.round(progress.value * 100)}%</span>}
      </div>
    </>
  );
}

type Lamp = "off" | "partial" | "done";

/** How far along a part is, and its short readout under the waypoint. */
function partStatus(part: Part, { progress }: LessonDetail, decisions: Decisions | undefined): { lamp: Lamp; reading: string } {
  const fraction = (done: number, total: number) => ({
    lamp: (total > 0 && done >= total ? "done" : done > 0 ? "partial" : "off") as Lamp,
    reading: `${done}/${total}`,
  });
  switch (part) {
    case "quiz":
      return fraction(progress.quiz.answered, progress.quiz.total);
    case "rebuild":
      return fraction(progress.exercises.passed, progress.exercises.total);
    case "options":
      if (progress.review.total === 0) return { lamp: "off", reading: "Compare" };
      return progress.review.reviewed ? { lamp: "done", reading: "Reviewed" } : { lamp: "off", reading: "Your call" };
    case "decisions":
      return { lamp: "off", reading: decisions ? plural(decisions.decisions.length, "card") : "…" };
    case "notebook":
      return { lamp: "off", reading: "Run" };
    case "explain":
      return { lamp: "off", reading: "Read" };
  }
}

/** The parts as waypoints: the plane marks the open part, legs light up as parts are done. */
function PartRoute({ parts, current, detail, decisions, go, mini = false }: RouteProps & { mini?: boolean }) {
  const lamps = parts.map((p) => partStatus(p, detail, decisions));
  return (
    <nav aria-label="Lesson parts">
      <ol className={`part-route${mini ? " is-mini" : ""}`} style={{ gridTemplateColumns: `repeat(${parts.length}, 1fr)` }}>
        {parts.map((p, i) => {
          const { label, code, icon: Icon } = PART[p];
          const here = p === current;
          return (
            <li key={p} className={`waypoint is-${lamps[i].lamp}${here ? " is-here" : ""}`}>
              {i > 0 && <span className={`route-leg is-${lamps[i - 1].lamp}`} aria-hidden />}
              <button type="button" onClick={() => go(p)} aria-current={here ? "step" : undefined} aria-label={mini ? label : undefined} title={mini ? label : undefined}>
                <span className="waypoint-node" aria-hidden>
                  {here ? <Plane size={mini ? 12 : 18} strokeWidth={1.75} /> : <Icon size={mini ? 10 : 14} strokeWidth={1.5} />}
                </span>
                {!mini && (
                  <span className="waypoint-text">
                    <span className="waypoint-code" aria-hidden>
                      {code}
                    </span>
                    <span className="waypoint-label">{label}</span>
                    <span className="waypoint-reading">{lamps[i].reading}</span>
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/** A fixed row of lights; unlit ones stay visible but dim, so a lit one stands out. */
function StatusLights({ detail: { lesson, staleness, progress } }: { detail: LessonDetail }) {
  const lights: { label: string; tone: "off" | "info" | "warning" | "danger" | "success"; title: string }[] = [
    {
      label: "Stale",
      tone: staleness.stale && !staleness.repo_missing ? "warning" : "off",
      title: staleness.stale ? "The code has changed since this lesson was made" : "The code matches the lesson",
    },
    {
      label: "No repo",
      tone: staleness.repo_missing ? "danger" : "off",
      title: staleness.repo_missing ? "The project folder for this lesson is gone" : "The project folder is there",
    },
    {
      label: "Dirty",
      tone: lesson.source?.includes_uncommitted ? "info" : "off",
      title: lesson.source?.includes_uncommitted ? "Made from uncommitted changes" : "Made from commits only",
    },
  ];
  if (completable(progress)) {
    lights.push({
      label: "Complete",
      tone: progress.value >= 1 ? "success" : "off",
      title: progress.value >= 1 ? "Everything in this lesson is done" : `${Math.round(progress.value * 100)}% done`,
    });
  }
  return (
    <div className="status-lights">
      {lights.map((l) => (
        <span key={l.label} className={`status-light is-${l.tone}`} title={l.title} aria-hidden={l.tone === "off"}>
          {l.label}
        </span>
      ))}
    </div>
  );
}

function SourceLine({ detail: { lesson } }: { detail: LessonDetail }) {
  const s = lesson.source;
  if (!s) return <span className="mono-sm muted">Not yet built</span>;
  const rows: [string, string | null][] = [
    ["repo", repoName(s.repo_path)],
    ["branch", s.branch],
    ["base", shortCommit(s.base_commit)],
    ["head", shortCommit(s.head_commit)],
    ["files", String(s.files.length)],
    ["python", lesson.environment?.python_version ?? null],
  ];
  return (
    <dl className="source-line" title={s.repo_path}>
      {rows
        .filter(([, v]) => v)
        .map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
    </dl>
  );
}

function ChangedFiles({ detail: { lesson, staleness } }: { detail: LessonDetail }) {
  if (!staleness.stale) return null;
  if (staleness.repo_missing) {
    return (
      <p className="mono-sm changed-files">
        <span className="danger">GONE</span> {lesson.source?.repo_path} — the lesson can't be compared with the current
        code.
      </p>
    );
  }
  return (
    <ul className="changed-files" aria-label={`${plural(staleness.changed.length, "file differs", "files differ")} since this lesson was made`}>
      {staleness.changed.map((f) => (
        <li key={f.path} className="mono-sm">
          <span className="warning">{f.change === "missing" ? "DEL" : "MOD"}</span> {f.path}
        </li>
      ))}
    </ul>
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

// Explain tab: explanation.md with an "On this page" outline of its sections.

import { useEffect, useMemo, useState } from "react";
import { api, useLoad } from "../api";
import { headings, Markdown } from "../components/Markdown";
import { Status } from "../components/ui";

export function ExplainTab({ lessonId }: { lessonId: string }) {
  // The lesson header already shows the title, so a leading "# Title" would repeat it.
  const text = useLoad(
    () => api.text(lessonId, "explanation.md").then((md) => md.replace(/^\s*#\s[^\n]*\n/, "")),
    [lessonId],
  );
  const outline = useMemo(() => headings(text.data ?? ""), [text.data]);
  const active = useActiveHeading(outline.map((h) => h.id));

  if (text.data === undefined) return <Status error={text.error} />;
  return (
    <div className="with-sidebar">
      {outline.length > 1 && (
        <aside className="sidebar outline-sidebar">
          <nav className="outline" aria-label="On this page">
            <h2 className="overline ink">On this page</h2>
            {outline.map((h) => (
              <a key={h.id} href={`#${h.id}`} className={h.id === active ? "is-active" : undefined}>
                {h.title}
              </a>
            ))}
          </nav>
        </aside>
      )}
      <article className="reading">
        <Markdown text={text.data} lessonId={lessonId} />
      </article>
    </div>
  );
}

/** The id of the last heading scrolled past the top of the viewport. */
function useActiveHeading(ids: string[]): string | undefined {
  const [active, setActive] = useState<string>();
  const key = ids.join("\n");
  useEffect(() => {
    const ids = key.split("\n");
    const update = () => {
      let current = ids[0];
      for (const id of ids) {
        const el = document.getElementById(id);
        if (el && el.getBoundingClientRect().top < 120) current = id;
      }
      setActive(current);
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, [key]);
  return active;
}

// Lesson Markdown (GitHub-flavoured), as in explanation.md and decisions.md.
// Relative links and images resolve to the lesson bundle's files; ```mermaid
// blocks become diagrams; Python blocks are highlighted. Raw HTML isn't rendered.
// Code references such as `src/pkg/mod.py:40-72` link to the notebook cell with
// that source_ref (spec §5.2).

import type { ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import { Link } from "react-router-dom";
import remarkGfm from "remark-gfm";
import { fileUrl } from "../api";
import { highlightPython } from "./highlight";
import { Mermaid } from "./Mermaid";

interface HastNode {
  type: string;
  value?: string;
  children?: HastNode[];
}

const textOf = (node?: HastNode): string =>
  node ? (node.type === "text" ? (node.value ?? "") : (node.children ?? []).map(textOf).join("")) : "";

export const slug = (text: string) =>
  text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s-]/gu, "")
    .trim()
    .replace(/\s+/g, "-");

const SOURCE_REF = /^[\w./-]+\.py:\d+(-\d+)?$/;

const isRelative = (url: string) => !/^([a-z][a-z0-9+.-]*:|\/|#)/i.test(url);

function components(lessonId: string, inline: boolean): Components {
  const resolve = (url?: string) => (url && isRelative(url) ? fileUrl(lessonId, url.replace(/^\.\//, "")) : url);
  return {
    ...(inline ? { p: ({ children }) => <>{children}</> } : {}),
    h2: ({ node, children }) => <h2 id={slug(textOf(node as HastNode))}>{children}</h2>,
    a: ({ href, children }) => {
      const external = !!href && /^https?:/i.test(href);
      return (
        <a href={resolve(href)} {...(external ? { target: "_blank", rel: "noreferrer" } : {})}>
          {children}
        </a>
      );
    },
    img: ({ src, alt }) => <img src={resolve(typeof src === "string" ? src : undefined)} alt={alt ?? ""} />,
    pre: ({ children }) => <>{children}</>,
    code: ({ className, children }) => {
      const lang = /language-(\S+)/.exec(className ?? "")?.[1];
      const code = String(children ?? "");
      // Fenced blocks have a language or end in a newline; inline code has neither.
      if (lang === undefined && !code.includes("\n")) {
        if (SOURCE_REF.test(code)) {
          return (
            <Link to={`/lessons/${encodeURIComponent(lessonId)}/notebook#src=${encodeURIComponent(code)}`} title="Show in the notebook">
              <code className="md-code">{children}</code>
            </Link>
          );
        }
        return <code className="md-code">{children}</code>;
      }
      const source = code.replace(/\n$/, "");
      if (lang === "mermaid") return <Mermaid code={source} />;
      return (
        <pre className="md-pre">
          <code>{lang === "python" || lang === "py" ? highlightPython(source) : source}</code>
        </pre>
      );
    },
  };
}

export function Markdown({ text, lessonId, inline = false }: { text: string; lessonId: string; inline?: boolean }): ReactNode {
  const body = (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components(lessonId, inline)}>
      {text}
    </ReactMarkdown>
  );
  return inline ? body : <div className="prose">{body}</div>;
}

/** The `## ` headings of a Markdown document (outside code fences), for an outline. */
export function headings(text: string): { id: string; title: string }[] {
  const found: { id: string; title: string }[] = [];
  let fence: string | null = null;
  for (const line of text.split("\n")) {
    const marker = /^\s*(`{3,}|~{3,})/.exec(line)?.[1];
    if (marker && (fence === null || marker.startsWith(fence))) fence = fence === null ? marker : null;
    else if (fence === null) {
      const m = /^##\s+(.+?)\s*#*\s*$/.exec(line);
      // Match the rendered heading's text: drop inline Markdown markers.
      if (m) {
        const title = m[1].replace(/[`*_]/g, "").replace(/\[([^\]]*)\]\([^)]*\)/g, "$1");
        found.push({ id: slug(title), title });
      }
    }
  }
  return found;
}

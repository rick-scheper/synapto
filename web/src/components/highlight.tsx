// A small Python highlighter that colours code with the `code-*` tokens
// (ported from the design system's CodeCell). Good enough for lesson snippets;
// it doesn't try to be a full lexer.

import type { ReactNode } from "react";

const KEYWORDS = new Set(
  ("def return import from as if elif else for while in not and or is None True False class with lambda " +
    "yield raise try except finally pass break continue assert async await").split(" "),
);

const TOKEN = /(#[^\n]*)|("""[\s\S]*?"""|'''[\s\S]*?'''|'[^'\n]*'|"[^"\n]*")|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][A-Za-z0-9_]*)|([\s\S])/g;

export function highlightPython(code: string): ReactNode[] {
  const out: ReactNode[] = [];
  let plain = "";
  let afterDef = false;
  let key = 0;
  for (const m of code.matchAll(TOKEN)) {
    const text = m[0];
    let cls: string | null = null;
    if (m[1]) cls = "c";
    else if (m[2]) cls = "s";
    else if (m[3]) cls = "n";
    else if (m[4]) {
      if (KEYWORDS.has(text)) cls = "k";
      else if (afterDef || code.charAt(m.index! + text.length) === "(") cls = "f";
    }
    if (m[4]) afterDef = text === "def" || text === "class";
    else if (!/\s/.test(text)) afterDef = false;

    if (cls) {
      if (plain) out.push(plain);
      plain = "";
      out.push(
        <span key={key++} className={`sy-tk-${cls}`}>
          {text}
        </span>,
      );
    } else plain += text;
  }
  if (plain) out.push(plain);
  return out;
}

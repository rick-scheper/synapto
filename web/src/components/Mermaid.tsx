// Renders a ```mermaid block, themed from the design tokens (brand book,
// "Diagrams"). Mermaid is large, so it loads only when a lesson has a diagram.

import { useEffect, useId, useState } from "react";
import { useTheme } from "../theme";
import { Badge } from "./ui";

function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function Mermaid({ code }: { code: string }) {
  const { theme } = useTheme();
  const id = `mermaid-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const [svg, setSvg] = useState<string>();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    import("mermaid").then(async ({ default: mermaid }) => {
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        theme: "base",
        fontFamily: token("--font-sans"),
        themeVariables: {
          background: token("--surface"),
          primaryColor: token("--surface-raised"),
          primaryBorderColor: token("--accent-deep"),
          primaryTextColor: token("--ink"),
          secondaryColor: token("--surface-raised"),
          tertiaryColor: token("--surface-sunken"),
          lineColor: token("--accent-deep"),
          textColor: token("--ink"),
          mainBkg: token("--surface-raised"),
          nodeBorder: token("--accent-deep"),
          clusterBkg: token("--surface-sunken"),
          clusterBorder: token("--line"),
          edgeLabelBackground: token("--surface"),
          fontSize: "14px",
        },
      });
      try {
        const { svg } = await mermaid.render(`${id}-${theme}`, code);
        if (live) (setSvg(svg), setFailed(false));
      } catch {
        if (live) setFailed(true);
      }
    });
    return () => {
      live = false;
    };
  }, [code, id, theme]);

  if (failed) {
    return (
      <figure className="diagram diagram-failed">
        <Badge tone="warning">Diagram didn't render</Badge>
        <pre className="md-pre">
          <code>{code}</code>
        </pre>
      </figure>
    );
  }
  return (
    <figure
      className="diagram"
      aria-busy={!svg}
      // Mermaid's own output, rendered with securityLevel "strict".
      dangerouslySetInnerHTML={svg ? { __html: svg } : undefined}
    />
  );
}

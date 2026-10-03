// A notebook cell's outputs (nbformat 4): streams, errors and rich display data.
// For display data the richest format we can show wins: Plotly, HTML (pandas
// tables), SVG, PNG/JPEG/GIF, Markdown, JSON, then plain text. HTML is inserted
// as markup, so its scripts don't run. Plotly is loaded only when a figure appears.

import { useEffect, useRef, useState } from "react";
import type { MimeBundle, Output } from "../api";
import { joinText, terminalText } from "../kernel";
import { Markdown } from "./Markdown";

const PLOTLY = "application/vnd.plotly.v1+json";
const IMAGES = ["image/png", "image/jpeg", "image/gif"];
// ANSI escape sequences, as in IPython's coloured tracebacks.
const ANSI = /\x1b\[[0-9;]*[A-Za-z]/g;

const text = (value: MimeBundle[string]) => (typeof value === "string" || Array.isArray(value) ? joinText(value) : JSON.stringify(value, null, 2));

export function Outputs({ outputs, lessonId }: { outputs: Output[]; lessonId: string }) {
  if (outputs.length === 0) return null;
  return (
    <div className="nb-outputs">
      {outputs.map((output, i) => (
        <OutputView key={i} output={output} lessonId={lessonId} />
      ))}
    </div>
  );
}

function OutputView({ output, lessonId }: { output: Output; lessonId: string }) {
  switch (output.output_type) {
    case "stream":
      return <pre className={`nb-out${output.name === "stderr" ? " is-stderr" : ""}`}>{terminalText(joinText(output.text))}</pre>;
    case "error": {
      const traceback = output.traceback.join("\n").replace(ANSI, "").trim();
      return <pre className="nb-out is-error">{traceback || `${output.ename}: ${output.evalue}`}</pre>;
    }
    default:
      return <MimeView data={output.data} lessonId={lessonId} />;
  }
}

function MimeView({ data, lessonId }: { data: MimeBundle; lessonId: string }) {
  if (PLOTLY in data) return <PlotlyView figure={data[PLOTLY] as PlotlyFigure} fallback={data} lessonId={lessonId} />;
  if ("text/html" in data) return <div className="nb-out nb-html" dangerouslySetInnerHTML={{ __html: text(data["text/html"]) }} />;
  if ("image/svg+xml" in data) {
    const src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(text(data["image/svg+xml"]))}`;
    return <div className="nb-out nb-media"><img src={src} alt="" /></div>;
  }
  const image = IMAGES.find((mime) => mime in data);
  if (image) {
    const src = `data:${image};base64,${text(data[image]).replace(/\s/g, "")}`;
    return <div className="nb-out nb-media"><img src={src} alt="" /></div>;
  }
  if ("text/markdown" in data) return <div className="nb-out nb-md"><Markdown text={text(data["text/markdown"])} lessonId={lessonId} /></div>;
  if ("application/json" in data) return <pre className="nb-out">{text(data["application/json"])}</pre>;
  if ("text/plain" in data) return <pre className="nb-out">{text(data["text/plain"])}</pre>;
  return <pre className="nb-out muted">[output in {Object.keys(data).join(", ") || "an unknown format"}, which the hub can't show]</pre>;
}

interface PlotlyFigure {
  data: unknown[];
  layout?: Record<string, unknown>;
  config?: Record<string, unknown>;
}

function PlotlyView({ figure, fallback, lessonId }: { figure: PlotlyFigure; fallback: MimeBundle; lessonId: string }) {
  const host = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    const el = host.current!;
    import("plotly.js-dist-min").then(
      ({ default: Plotly }) => {
        if (!live) return;
        Plotly.newPlot(el, figure.data, { autosize: true, ...figure.layout }, { responsive: true, displaylogo: false, ...figure.config });
      },
      () => live && setFailed(true),
    );
    return () => {
      live = false;
      import("plotly.js-dist-min").then(({ default: Plotly }) => Plotly.purge(el), () => {});
    };
  }, [figure]);

  if (failed) {
    const { [PLOTLY]: _, ...rest } = fallback;
    return <MimeView data={rest} lessonId={lessonId} />;
  }
  return <div className="nb-out nb-media" ref={host} />;
}

// The Mermaid check behind `synapto validate` (spec §8), run with Node: reads a
// JSON array of diagram sources on stdin and writes a JSON array holding, per
// source, null when it parses or Mermaid's error message when it doesn't. It
// is built from the same Mermaid the hub renders with, so a diagram that passes
// here renders there.

import mermaid from "mermaid";

// Node's globals; the web tsconfig has no Node types.
declare const process: {
  stdin: AsyncIterable<string> & { setEncoding(encoding: "utf8"): void };
  stdout: { write(text: string): void };
};

mermaid.initialize({ startOnLoad: false });

process.stdin.setEncoding("utf8");
let input = "";
for await (const chunk of process.stdin) input += chunk;

const results: (string | null)[] = [];
for (const source of JSON.parse(input) as string[]) {
  try {
    await mermaid.parse(source);
    results.push(null);
  } catch (err) {
    results.push(err instanceof Error ? err.message : String(err));
  }
}
process.stdout.write(JSON.stringify(results));

// Removes a heading section (e.g. "## How to Build and Run") and everything nested under it,
// stopping at the next heading of the same or higher level (or EOF). Case-insensitive match.
export function stripSection(markdown: string, heading: string): string {
  const headingRe = /^(#{1,6})\s+(.*)$/;
  const target = heading.trim().toLowerCase();
  const out: string[] = [];
  let skipping = false;
  let skipLevel = 0;

  for (const line of markdown.split('\n')) {
    const match = headingRe.exec(line);
    if (match) {
      const level = match[1].length;
      const text = match[2].trim().toLowerCase();
      if (skipping && level <= skipLevel) {
        skipping = false;
      }
      if (!skipping && text === target) {
        skipping = true;
        skipLevel = level;
        continue;
      }
    }
    if (!skipping) out.push(line);
  }

  return out.join('\n');
}

// Splits markdown right after the title's first section (e.g. "# Title" + "## Problem
// Statement" + its paragraph) so callers can insert content — like difficulty/topic badges —
// directly under the description instead of after the full README (Requirements,
// Instructions, etc). Returns [firstSection, rest]; rest is '' if there's nothing to split.
export function splitAfterFirstSection(markdown: string): [string, string] {
  const headingRe = /^(#{1,6})\s+(.*)$/;
  const lines = markdown.split('\n');
  const headings: { line: number; level: number }[] = [];
  lines.forEach((line, i) => {
    const match = headingRe.exec(line);
    if (match) headings.push({ line: i, level: match[1].length });
  });

  // Need a title heading plus at least one section heading after it to find a boundary.
  if (headings.length < 2) return [markdown, ''];

  const sectionLevel = headings[1].level;
  const splitAt = headings.slice(2).find((h) => h.level <= sectionLevel);
  if (!splitAt) return [markdown, ''];

  return [lines.slice(0, splitAt.line).join('\n'), lines.slice(splitAt.line).join('\n')];
}

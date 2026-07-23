export interface SymbolEntry {
  name: string;
  line: number;
}

const JAVA_KEYWORDS = new Set(['if', 'for', 'while', 'switch', 'catch', 'synchronized', 'return']);
const JS_KEYWORDS = new Set(['if', 'for', 'while', 'switch', 'catch', 'function']);

function extractJavaSymbols(content: string): SymbolEntry[] {
  const methodRe = /^\s*(?:public|private|protected|static|final|synchronized|abstract|native|\s)+[\w<>[\],\s]+?\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{/;
  const classRe = /^\s*(?:public|private|protected|static|final|abstract|\s)*\b(?:class|interface|enum)\s+(\w+)/;
  const results: SymbolEntry[] = [];
  content.split('\n').forEach((line, i) => {
    const classMatch = classRe.exec(line);
    if (classMatch) {
      results.push({ name: classMatch[1], line: i + 1 });
      return;
    }
    const methodMatch = methodRe.exec(line);
    if (methodMatch && !JAVA_KEYWORDS.has(methodMatch[1])) {
      results.push({ name: methodMatch[1], line: i + 1 });
    }
  });
  return results;
}

function extractPythonSymbols(content: string): SymbolEntry[] {
  const defRe = /^\s*def\s+(\w+)\s*\(/;
  const classRe = /^\s*class\s+(\w+)/;
  const results: SymbolEntry[] = [];
  content.split('\n').forEach((line, i) => {
    const classMatch = classRe.exec(line);
    if (classMatch) {
      results.push({ name: classMatch[1], line: i + 1 });
      return;
    }
    const defMatch = defRe.exec(line);
    if (defMatch) {
      results.push({ name: defMatch[1], line: i + 1 });
    }
  });
  return results;
}

function extractGenericJsSymbols(content: string): SymbolEntry[] {
  const classRe = /^\s*(?:export\s+)?(?:default\s+)?class\s+(\w+)/;
  const fnRe = /^\s*(?:export\s+)?(?:default\s+)?function\s+(\w+)\s*\(/;
  const arrowRe = /^\s*(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>/;
  const methodRe = /^\s*(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{/;
  const results: SymbolEntry[] = [];
  content.split('\n').forEach((line, i) => {
    const classMatch = classRe.exec(line);
    if (classMatch) { results.push({ name: classMatch[1], line: i + 1 }); return; }
    const fnMatch = fnRe.exec(line);
    if (fnMatch) { results.push({ name: fnMatch[1], line: i + 1 }); return; }
    const arrowMatch = arrowRe.exec(line);
    if (arrowMatch) { results.push({ name: arrowMatch[1], line: i + 1 }); return; }
    const methodMatch = methodRe.exec(line);
    if (methodMatch && !JS_KEYWORDS.has(methodMatch[1])) {
      results.push({ name: methodMatch[1], line: i + 1 });
    }
  });
  return results;
}

function regexSymbolsFor(path: string, content: string): SymbolEntry[] {
  if (path.endsWith('.java')) return extractJavaSymbols(content);
  if (path.endsWith('.py')) return extractPythonSymbols(content);
  return extractGenericJsSymbols(content);
}

/**
 * Best-effort outline: for JS/TS, prefer Monaco's real TS language-service navigation tree
 * (accurate, handles nesting). Everything else — and JS/TS if the worker isn't ready yet —
 * falls back to a regex signature scan, since Monaco ships no Java/Python language service.
 */
export async function extractSymbols(
  path: string,
  content: string,
  monacoInstance: any,
  model: any
): Promise<SymbolEntry[]> {
  const isJsTs = /\.(js|jsx|ts|tsx|mjs|cjs)$/.test(path);
  if (isJsTs && monacoInstance?.languages?.typescript && model) {
    try {
      const getWorker = path.endsWith('.ts') || path.endsWith('.tsx')
        ? monacoInstance.languages.typescript.getTypeScriptWorker
        : monacoInstance.languages.typescript.getJavaScriptWorker;
      const workerAccessor = await getWorker();
      const client = await workerAccessor(model.uri);
      const tree = await client.getNavigationTree(model.uri.toString());
      const out: SymbolEntry[] = [];
      const walk = (item: any) => {
        if (item.spans?.[0]) {
          const pos = model.getPositionAt(item.spans[0].start);
          out.push({ name: item.text, line: pos.lineNumber });
        }
        item.childItems?.forEach(walk);
      };
      tree.childItems?.forEach(walk);
      if (out.length > 0) return out.sort((a, b) => a.line - b.line);
    } catch {
      // Worker not ready / not registered for this file — fall through to regex.
    }
  }
  return regexSymbolsFor(path, content);
}

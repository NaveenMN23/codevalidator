import { useState } from 'react';
import { CheckCircle, XCircle, AlertTriangle, MinusCircle, ChevronDown, ChevronUp } from 'lucide-react';
import type { TestCaseResult } from '../workspace.types';

interface TestResultsListProps {
  results: TestCaseResult[];
}

const STATUS_ICON: Record<TestCaseResult['status'], React.ReactNode> = {
  PASSED: <CheckCircle size={12} className="text-green-600 dark:text-green-400 shrink-0" />,
  FAILED: <XCircle size={12} className="text-red-500 shrink-0" />,
  ERRORED: <AlertTriangle size={12} className="text-amber-500 shrink-0" />,
  SKIPPED: <MinusCircle size={12} className="text-text-muted shrink-0" />,
};

function testKey(test: TestCaseResult, index: number): string {
  return `${test.className}.${test.name}-${index}`;
}

export function TestResultsList({ results }: TestResultsListProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const passed = results.filter((r) => r.status === 'PASSED').length;
  const failed = results.filter((r) => r.status === 'FAILED' || r.status === 'ERRORED').length;

  return (
    <div className="text-[10px]">
      <div className="flex items-center gap-3 mb-2 font-bold uppercase tracking-wide text-[9px]">
        <span className="text-green-600 dark:text-green-400">{passed} passed</span>
        {failed > 0 && <span className="text-red-500">{failed} failed</span>}
      </div>
      <div className="space-y-1">
        {results.map((test, index) => {
          const key = testKey(test, index);
          const isProblem = test.status === 'FAILED' || test.status === 'ERRORED';
          const isExpanded = expanded.has(key);

          return (
            <div
              key={key}
              className="border border-border-main rounded-lg overflow-hidden bg-panel/50"
            >
              <div className="flex items-center gap-2 px-2.5 py-1.5">
                {STATUS_ICON[test.status]}
                <span className="font-mono text-text-main truncate">
                  {test.className ? `${test.className}.` : ''}
                  {test.name}
                </span>
                {isProblem && test.stackTrace && (
                  <button
                    onClick={() => toggle(key)}
                    className="ml-auto flex items-center gap-0.5 text-text-muted hover:text-text-main shrink-0 text-[8px] font-bold uppercase"
                  >
                    {isExpanded ? 'Hide trace' : 'Full trace'}
                    {isExpanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
                  </button>
                )}
              </div>

              {isProblem && (test.expected !== null || test.actual !== null || test.message) && (
                <div className="px-2.5 pb-2 space-y-1">
                  {test.expected !== null || test.actual !== null ? (
                    <div className="font-mono text-[9px] bg-black/5 dark:bg-black/30 rounded p-1.5 space-y-0.5">
                      <div>
                        <span className="text-text-muted">expected: </span>
                        <span className="text-green-600 dark:text-green-400">{test.expected ?? '—'}</span>
                      </div>
                      <div>
                        <span className="text-text-muted">actual: </span>
                        <span className="text-red-500">{test.actual ?? '—'}</span>
                      </div>
                    </div>
                  ) : (
                    test.message && (
                      <p className="text-red-500 font-mono text-[9px] whitespace-pre-wrap">{test.message}</p>
                    )
                  )}

                  {isExpanded && test.stackTrace && (
                    <pre className="bg-black/10 dark:bg-black/30 text-text-muted text-[8px] p-2 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono mt-1">
                      {test.stackTrace}
                    </pre>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

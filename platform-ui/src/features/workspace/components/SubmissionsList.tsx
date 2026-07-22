import { useEffect, useState } from 'react';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import type { SubmissionSummary } from '../workspace.types';
import { fetchSubmissions } from '../api';

interface SubmissionsListProps {
  challengeId: string;
  refreshKey: number;
  onViewSubmission: (submissionId: string) => void;
}

export function SubmissionsList({ challengeId, refreshKey, onViewSubmission }: SubmissionsListProps) {
  const [submissions, setSubmissions] = useState<SubmissionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setSubmissions(null);
    setError(null);
    fetchSubmissions(challengeId)
      .then((result) => {
        if (!cancelled) setSubmissions(result);
      })
      .catch(() => {
        if (!cancelled) setError('Failed to load submissions.');
      });
    return () => {
      cancelled = true;
    };
  }, [challengeId, refreshKey]);

  if (error) {
    return <p className="p-4 text-sm text-red-500">{error}</p>;
  }

  if (submissions === null) {
    return (
      <div className="flex h-full items-center justify-center text-text-muted">
        <Loader2 className="animate-spin" size={20} />
      </div>
    );
  }

  if (submissions.length === 0) {
    return <div className="flex h-full items-center justify-center p-4 text-[14px] text-text-muted">No submissions yet.</div>;
  }

  return (
    <div className="text-[11px] p-2 space-y-1">
      {submissions.map((submission) => {
        const passed = submission.status === 'COMPLETED';
        const formatted = new Date(submission.submittedAt).toLocaleString(undefined, {
          dateStyle: 'medium',
          timeStyle: 'short',
        });

        return (
          <button
            key={submission.id}
            onClick={() => onViewSubmission(submission.id)}
            className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg border border-border-main bg-panel/50 hover:bg-black/5 dark:hover:bg-white/5 transition-all text-left"
          >
            {passed ? (
              <CheckCircle size={13} className="text-green-600 dark:text-green-400 shrink-0" />
            ) : (
              <XCircle size={13} className="text-red-500 shrink-0" />
            )}
            <span className="flex-grow min-w-0">
              <span className="block text-text-main font-medium truncate">
                {passed ? 'Accepted' : 'Failed'}
                {submission.score !== null && <span className="text-text-muted"> · {submission.score}</span>}
              </span>
              <span className="block text-text-muted">{formatted}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

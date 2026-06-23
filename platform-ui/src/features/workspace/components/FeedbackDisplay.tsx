import type { GradingResult } from '../workspace.types';
import { CheckCircle, XCircle } from 'lucide-react';

interface FeedbackDisplayProps {
  result: GradingResult;
}

export function FeedbackDisplay({ result }: FeedbackDisplayProps) {
  const { status, logs } = result;

  if (status === 'FAILED') {
    return (
      <div className="p-4 bg-red-500/5 border border-red-500/20 rounded-md">
        <h3 className="text-sm font-bold flex items-center gap-2 mb-2 text-red-500">
          <XCircle size={16} />
          Validation Failed
        </h3>
        <p className="text-xs text-text-main mb-3">Your code failed the basic validation tests. Fix the errors below and submit again.</p>
        <div className="bg-bg-elevated p-3 rounded font-mono text-[10px] text-red-400 overflow-x-auto whitespace-pre">
          {logs || 'No error logs available.'}
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 bg-green-500/5 border border-green-500/20 rounded-md">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-2 text-green-500">
        <CheckCircle size={16} />
        Validation Successful
      </h3>
      <p className="text-xs text-text-main mb-3">Tests passed successfully!</p>
      <div className="bg-bg-elevated p-3 rounded font-mono text-[10px] text-green-400 overflow-x-auto whitespace-pre">
        {logs || 'Tests passed successfully.'}
      </div>
    </div>
  );
}

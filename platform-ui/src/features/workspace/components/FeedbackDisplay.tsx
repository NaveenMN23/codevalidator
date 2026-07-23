import type { GradingResult } from '../workspace.types';
import { CheckCircle, XCircle, Loader, Target, Zap, MessageSquare, Award, BookOpen } from 'lucide-react';
import { TestResultsList } from './TestResultsList';

interface FeedbackDisplayProps {
  result: GradingResult;
}

function AiBubble({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2">
      <div className="w-6 h-6 rounded-full bg-primary/15 text-primary flex items-center justify-center shrink-0 mt-0.5 text-[7px] font-black">
        AI
      </div>
      <div className="bg-panel border border-border-main text-[10px] px-3 py-2.5 rounded-2xl rounded-tl-sm max-w-[88%] text-text-main leading-relaxed">
        {children}
      </div>
    </div>
  );
}

function UserBubble({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex justify-end">
      <div className="bg-primary text-background text-[10px] px-3 py-2 rounded-2xl rounded-br-sm max-w-[80%] leading-relaxed">
        {children}
      </div>
    </div>
  );
}

export function FeedbackDisplay({ result }: FeedbackDisplayProps) {
  const { feedback, status, logs, testResults } = result;
  const hasTestResults = testResults && testResults.length > 0;

  if (status === 'PENDING') {
    return (
      <div className="p-4 space-y-3 animate-in fade-in duration-300">
        <UserBubble>Code submitted for review</UserBubble>
        <AiBubble>
          <div className="flex items-center gap-2">
            <Loader className="animate-spin text-primary shrink-0" size={12} />
            <span>Analyzing your submission...</span>
          </div>
        </AiBubble>
      </div>
    );
  }

  if (status === 'FAILED' || status === 'TIMEOUT') {
    return (
      <div className="p-4 space-y-3 animate-in fade-in duration-300">
        <UserBubble>Code submitted for review</UserBubble>
        <AiBubble>
          <div className="flex items-center gap-1.5 mb-2 text-red-500 font-bold text-[9px] uppercase tracking-wide">
            <XCircle size={11} />
            Validation Failed
          </div>
          <p className="mb-2">Your code failed the basic validation tests. Fix the errors and try again.</p>
          {hasTestResults ? (
            <TestResultsList results={testResults!} />
          ) : (
            logs && (
              <pre className="bg-black/10 dark:bg-black/30 text-red-400 text-[8px] p-2 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono mt-2">
                {logs}
              </pre>
            )
          )}
        </AiBubble>
      </div>
    );
  }

  if (!feedback) {
    return (
      <div className="p-4 space-y-3 animate-in fade-in duration-300">
        <UserBubble>Code submitted for review</UserBubble>
        <AiBubble>
          <div className="flex items-center gap-1.5 mb-2 text-green-600 dark:text-green-400 font-bold text-[9px] uppercase tracking-wide">
            <CheckCircle size={11} />
            Tests Passed
          </div>
          <p>Basic tests passed successfully! Detailed AI evaluation is available on the premium tier.</p>
          {hasTestResults ? (
            <TestResultsList results={testResults!} />
          ) : (
            logs && (
              <pre className="bg-black/5 dark:bg-black/30 text-green-600 dark:text-green-400 text-[8px] p-2 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono mt-2">
                {logs}
              </pre>
            )
          )}
        </AiBubble>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-3 animate-in fade-in slide-in-from-bottom-2 duration-500 pb-6">
      <UserBubble>Code submitted for review</UserBubble>

      <AiBubble>
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-1.5 text-green-600 dark:text-green-400 font-bold text-[9px] uppercase tracking-wide">
            <Target size={11} />
            Correctness
          </div>
          <span className="text-[9px] font-bold text-green-600 dark:text-green-400">
            {feedback.correctness.score}/10
          </span>
        </div>
        <p>{feedback.correctness.finding}</p>
      </AiBubble>

      <AiBubble>
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-1.5 text-primary font-bold text-[9px] uppercase tracking-wide">
            <Zap size={11} />
            Efficiency
          </div>
          <span className="text-[9px] font-bold text-primary">
            {feedback.efficiency.score}/10
          </span>
        </div>
        <p>{feedback.efficiency.finding}</p>
      </AiBubble>

      <AiBubble>
        <div className="flex items-center gap-1.5 mb-2 text-text-muted font-bold text-[9px] uppercase tracking-wide">
          <MessageSquare size={11} />
          Interviewer
          {feedback.followUp.type === 'IMPLEMENTATION' && (
            <span className="bg-primary/15 text-primary text-[7px] font-black px-1.5 py-0.5 rounded ml-auto">
              CODE CHANGE REQUESTED
            </span>
          )}
        </div>
        <p className="italic">"{feedback.followUp.content}"</p>
      </AiBubble>

      <AiBubble>
        <div className="flex items-center gap-1.5 mb-1.5 text-text-muted font-bold text-[9px] uppercase tracking-wide">
          <Award size={11} />
          Performance Summary
        </div>
        <p className="whitespace-pre-wrap">{feedback.summary}</p>
      </AiBubble>

      {feedback.examples && feedback.examples.length > 0 && (
        <AiBubble>
          <div className="flex items-center gap-1.5 mb-2 text-text-muted font-bold text-[9px] uppercase tracking-wide">
            <BookOpen size={11} />
            Worked Examples
          </div>
          <div className="space-y-2.5">
            {feedback.examples.map((ex, i) => (
              <div key={i} className={i > 0 ? 'pt-2.5 border-t border-border-main' : ''}>
                <p><span className="font-bold text-text-muted">Input:</span> {ex.input}</p>
                <p><span className="font-bold text-text-muted">Expected:</span> {ex.expectedOutput}</p>
                <p className="text-text-muted mt-0.5">{ex.explanation}</p>
              </div>
            ))}
          </div>
        </AiBubble>
      )}
    </div>
  );
}

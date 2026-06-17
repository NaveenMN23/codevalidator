import type { GradingResult } from '../workspace.types';
import { CheckCircle, MessageSquare, Award, Zap, Target, Loader, XCircle } from 'lucide-react';

interface FeedbackDisplayProps {
  result: GradingResult;
}

export function FeedbackDisplay({ result }: FeedbackDisplayProps) {
  const { feedback, status, logs } = result;

  if (status === 'PENDING') {
    return (
      <div className="p-8 flex flex-col items-center justify-center text-center gap-4">
        <Loader className="animate-spin text-primary" size={40} />
        <div>
          <h3 className="text-sm font-bold text-text-main">Grading in Progress</h3>
          <p className="text-xs text-text-muted mt-1">We are running your code against our test suite and analyzing it with AI.</p>
        </div>
      </div>
    );
  }

  if (status === 'FAILED' || status === 'TIMEOUT') {
    return (
      <div className="p-4 bg-red-500/5 border border-red-500/20 rounded-md">
        <h3 className="text-sm font-bold flex items-center gap-2 mb-2 text-red-500">
          <XCircle size={16} />
          Validation Failed
        </h3>
        <p className="text-xs text-text-main mb-3">Your code failed the basic validation tests. Fix the errors below and submit again.</p>
        <div className="bg-black/20 p-3 rounded font-mono text-[10px] text-red-400 overflow-x-auto whitespace-pre">
          {logs || 'No error logs available.'}
        </div>
      </div>
    );
  }

  if (!feedback) {
    return (
      <div className="p-4 bg-green-500/5 border border-green-500/20 rounded-md">
        <h3 className="text-sm font-bold flex items-center gap-2 mb-2 text-green-500">
          <CheckCircle size={16} />
          Validation Successful
        </h3>
        <p className="text-xs text-text-main mb-3">Basic tests passed successfully! Since you are on a free tier, detailed AI evaluation is not available.</p>
        <div className="bg-black/20 p-3 rounded font-mono text-[10px] text-green-400 overflow-x-auto whitespace-pre">
          {logs || 'Tests passed successfully.'}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-500 pb-8">
      {/* Correctness Layer */}
      <div className="p-3 bg-green-500/5 border border-green-500/20 rounded-md">
        <h4 className="text-[10px] font-black uppercase tracking-widest text-green-500 mb-1.5 flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Target size={12} />
            Layer 1: Correctness
          </div>
          <span className="bg-green-500/10 px-1.5 py-0.5 rounded text-[9px]">{feedback.correctness.score}/10</span>
        </h4>
        <p className="text-xs text-text-main leading-relaxed">{feedback.correctness.finding}</p>
      </div>

      {/* Efficiency Layer */}
      <div className="p-3 bg-blue-500/5 border border-blue-500/20 rounded-md">
        <h4 className="text-[10px] font-black uppercase tracking-widest text-blue-500 mb-1.5 flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Zap size={12} />
            Layer 2: Efficiency
          </div>
          <span className="bg-blue-500/10 px-1.5 py-0.5 rounded text-[9px]">{feedback.efficiency.score}/10</span>
        </h4>
        <p className="text-xs text-text-main leading-relaxed">{feedback.efficiency.finding}</p>
      </div>

      {/* Follow-up / Persona Layer */}
      <div className="p-4 bg-primary/5 border border-primary/20 rounded-lg relative overflow-hidden">
        <div className="absolute top-0 right-0 p-2 opacity-5">
          <MessageSquare size={64} />
        </div>
        <h4 className="text-[10px] font-black uppercase tracking-widest text-primary mb-3 flex items-center gap-1.5">
          <MessageSquare size={12} />
          Interviewer Follow-up ({feedback.followUp.type})
        </h4>
        <p className="text-sm text-text-main font-medium italic mb-4 leading-relaxed relative z-10">
          "{feedback.followUp.content}"
        </p>
        <div className="flex items-center justify-between">
           <div className="text-[9px] text-text-muted font-bold uppercase tracking-tighter">
            Senior Engineer Interviewer
          </div>
          {feedback.followUp.type === 'IMPLEMENTATION' && (
             <div className="bg-primary/20 text-primary text-[8px] font-black px-1.5 py-0.5 rounded">CODE CHANGE REQUESTED</div>
          )}
        </div>
      </div>

      {/* Session Summary */}
      <div className="p-4 bg-panel border border-border-main rounded-lg shadow-sm">
        <h4 className="text-[10px] font-black uppercase tracking-widest text-text-muted mb-2.5 flex items-center gap-1.5">
          <Award size={12} />
          AI Performance Summary
        </h4>
        <p className="text-xs text-text-main leading-relaxed whitespace-pre-wrap">{feedback.summary}</p>
      </div>
    </div>
  );
}

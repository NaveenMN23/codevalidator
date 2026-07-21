import { FileClock, RotateCcw } from 'lucide-react';

interface DraftResumeDialogProps {
  updatedAt: string;
  onContinue: () => void;
  onStartOver: () => void;
}

export function DraftResumeDialog({ updatedAt, onContinue, onStartOver }: DraftResumeDialogProps) {
  const formatted = new Date(updatedAt).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });

  return (
    <div className="flex h-full items-center justify-center bg-background text-text-muted">
      <div className="flex flex-col items-center gap-4 max-w-md text-center p-6 rounded-2xl border border-border-main bg-panel">
        <FileClock className="text-primary" size={40} />
        <p className="text-text-main font-medium">Resume your saved draft?</p>
        <p className="text-sm">
          You have work in progress on this challenge, last saved <span className="text-text-main font-medium">{formatted}</span>.
        </p>
        <div className="flex items-center gap-3 mt-2">
          <button
            onClick={onStartOver}
            className="flex items-center gap-2 px-4 py-2 rounded border border-border-main text-text-main hover:bg-black/5 dark:hover:bg-white/5 transition-all"
          >
            <RotateCcw size={16} />
            Start Over
          </button>
          <button
            onClick={onContinue}
            className="flex items-center gap-2 px-4 py-2 rounded bg-primary text-white hover:opacity-90 transition-opacity"
          >
            Continue Draft
          </button>
        </div>
      </div>
    </div>
  );
}

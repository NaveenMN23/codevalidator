import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Editor from '@monaco-editor/react';
import Split from 'react-split';
import ReactMarkdown from 'react-markdown';
import { TerminalComponent, type TerminalHandle } from './Terminal';
import { FileExplorer } from './FileExplorer';
import { FeedbackDisplay } from './FeedbackDisplay';
import { TestResultsList } from './TestResultsList';
import { DraftResumeDialog } from './DraftResumeDialog';
import { SubmissionsList } from './SubmissionsList';
import {
  Play, Send, RefreshCcw, LayoutGrid, BookOpen,
  ArrowLeft, ChevronUp, ChevronDown, ChevronLeft, ChevronRight, Terminal as TerminalIcon,
  RotateCcw, Sparkles, Sun, Moon, AlertTriangle, WrapText, Lock, ListTree, Hourglass,
  History, X, Tag, Pause, Square
} from 'lucide-react';
import { useAppStore } from '../../../store';
import { fetchChallenge, fetchChallengeFiles, fetchDraft, saveDraft, submitChallenge, deleteDraft, runChallenge, openWorkspaceSession, fetchSubmissionDetail } from '../api';
import type { DraftData } from '../api';
import type { GradingResult, TestCaseResult, SubmissionDetail } from '../workspace.types';
import { extractSymbols, type SymbolEntry } from '../outline';
import { isLockedPath } from '../fileLocking';
import { stripSection } from '../markdown';
import './Workspace.css';

// Plain in-memory file tree — same shape WebContainer's API used (kept for compatibility
// with FileExplorer's existing duck-typed rendering), but no longer backed by an actual
// WebContainer instance; everything here is just React state.
type FileNode = { file: { contents: string } } | { directory: FileTree };
type FileTree = Record<string, FileNode>;

// Fast non-cryptographic checksum (FNV-1a) used purely to detect "did the draft actually
// change since the last save" — not a security primitive, collisions are an acceptable risk.
function hashFiles(flatFiles: Record<string, string>): string {
  const serialized = JSON.stringify(flatFiles, Object.keys(flatFiles).sort());
  let hash = 0x811c9dc5;
  for (let i = 0; i < serialized.length; i++) {
    hash ^= serialized.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(16);
}

// Horizontal top tab, LeetCode-style — replaces the old vertical icon-only Activity Bar.
function PanelTab({ icon: Icon, label, active, pulse, onClick }: {
  icon: React.ComponentType<{ size?: number }>;
  label: string;
  active: boolean;
  pulse?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-3 py-2 text-[14px] border-b-2 shrink-0 transition-all cursor-pointer ${
        active
          ? 'border-primary text-primary bg-primary/5'
          : `border-transparent text-text-muted hover:text-text-main hover:bg-black/5 dark:hover:bg-white/5 ${pulse ? 'animate-pulse text-primary' : ''}`
      }`}
    >
      <Icon size={14} />
      {label}
    </button>
  );
}

// Vertical icon+label used in the collapsed rail — text runs top-to-bottom so the full tab
// set stays legible even at ~36px wide, instead of collapsing to a single bare chevron.
function CollapsedTab({ icon: Icon, label, active, onClick }: {
  icon: React.ComponentType<{ size?: number }>;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex flex-col items-center gap-2 py-3 w-full transition-all cursor-pointer ${
        active ? 'text-text-main' : 'text-text-muted hover:text-text-main'
      }`}
    >
      <Icon size={14} />
      <span
        style={{ writingMode: 'vertical-rl' }}
        className={`text-[11px] tracking-wide ${active ? 'font-bold' : 'font-medium'}`}
      >
        {label}
      </span>
    </button>
  );
}

const DIFFICULTY_STYLES: Record<string, { color: string; bg: string; label: string }> = {
  EASY: { color: 'var(--color-easy)', bg: 'var(--color-easy-bg)', label: 'Easy' },
  MEDIUM: { color: 'var(--color-medium)', bg: 'var(--color-medium-bg)', label: 'Medium' },
  HARD: { color: 'var(--color-hard)', bg: 'var(--color-hard-bg)', label: 'Hard' },
};

export function Workspace() {
  const { challengeId } = useParams<{ challengeId: string }>();
  const navigate = useNavigate();
  const { user, theme, setTheme } = useAppStore();

  const [files, setFiles] = useState<FileTree | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [openFiles, setOpenFiles] = useState<string[]>([]);
  const [terminal, setTerminal] = useState<any>(null);
  const [isBooting, setIsBooting] = useState(true);
  const [bootError, setBootError] = useState<string | null>(null);
  const [bootRetryKey, setBootRetryKey] = useState(0);
  const [pendingDraft, setPendingDraft] = useState<DraftData | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitStatus, setSubmitStatus] = useState<string | null>(null);
  const [gradingResult, setGradingResult] = useState<GradingResult | null>(null);
  const [runTestResults, setRunTestResults] = useState<TestCaseResult[] | null>(null);
  const [challengeMeta, setChallengeMeta] = useState<any>(null);
  // Single VS Code-style sidebar: one panel visible at a time, switched via the Activity Bar.
  // Explorer/Description/Submissions/Feedback used to be separate toggled panels — consolidated
  // back into one, matching the Activity Bar pattern this file had before it regressed.
  type PanelKey = 'explorer' | 'problem' | 'submissions' | 'feedback';
  const [activePanel, setActivePanel] = useState<PanelKey | null>('problem');
  const [showTerminal, setShowTerminal] = useState(false);
  const [viewingSubmission, setViewingSubmission] = useState<SubmissionDetail | null>(null);
  const [submissionsRefreshKey, setSubmissionsRefreshKey] = useState(0);
  const [timeLeft, setTimeLeft] = useState(3600); // 60 minutes default
  const [timerState, setTimerState] = useState<'RUNNING' | 'PAUSED'>('RUNNING');
  const isB2C = true; // Timer controls are configurable only for B2C
  const [wordWrap, setWordWrap] = useState<'off' | 'on'>('off');
  const [showOutline, setShowOutline] = useState(false);
  const [symbols, setSymbols] = useState<SymbolEntry[]>([]);

  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const terminalInstanceRef = useRef<any>(null);
  const terminalHandleRef = useRef<TerminalHandle | null>(null);
  const editorRef = useRef<any>(null);
  const monacoRef = useRef<any>(null);
  // Hash of the files as they last existed in the draft (either just loaded, or just
  // saved) — compared locally against the current files before autosaving, so we never
  // need a network round-trip just to check whether anything actually changed.
  const lastSavedHashRef = useRef<string | null>(null);
  const timeLeftRef = useRef(timeLeft);
  // Absolute wall-clock deadline the countdown reads from every tick, instead of just
  // decrementing a counter — setInterval's ~1000ms period drifts (and background-tab
  // throttling makes it worse), an absolute deadline self-corrects regardless.
  const deadlineRef = useRef<number | null>(null);
  // Remembers the last non-null panel so the collapse strip can reopen the same tab instead
  // of always defaulting back to "problem".
  const lastPanelRef = useRef<PanelKey>('problem');

  // Timer logic — self-corrects against deadlineRef rather than trusting the interval period.
  useEffect(() => {
    const timer = setInterval(() => {
      if (timerState === 'PAUSED' || deadlineRef.current == null) return;
      const remaining = Math.max(0, Math.round((deadlineRef.current - Date.now()) / 1000));
      setTimeLeft(remaining);
    }, 1000);
    return () => clearInterval(timer);
  }, [timerState]);

  const handlePauseTimer = () => {
    setTimerState('PAUSED');
  };

  const handleResumeTimer = () => {
    deadlineRef.current = Date.now() + timeLeft * 1000;
    setTimerState('RUNNING');
  };

  const handleRestartTimer = () => {
    setTimeLeft(3600);
    deadlineRef.current = Date.now() + 3600 * 1000;
    setTimerState('RUNNING');
  };

  const handleStopTimer = () => {
    setTimeLeft(3600);
    setTimerState('PAUSED');
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const selectPanel = (key: PanelKey) => {
    lastPanelRef.current = key;
    setActivePanel(key);
  };

  const unflattenFiles = (flatFiles: Record<string, string>): FileTree => {
    const tree: FileTree = {};
    for (const [path, content] of Object.entries(flatFiles)) {
      const parts = path.split('/');
      let current: any = tree;
      for (let i = 0; i < parts.length; i++) {
        const part = parts[i];
        if (i === parts.length - 1) {
          current[part] = { file: { contents: content } };
        } else {
          if (!current[part]) {
            current[part] = { directory: {} };
          }
          current = current[part].directory;
        }
      }
    }
    return tree;
  };

  const flattenFiles = (nestedFiles: any, prefix = ''): Record<string, string> => {
    let flat: Record<string, string> = {};
    if (!nestedFiles) return flat;
    for (const [name, entry] of Object.entries(nestedFiles)) {
      const path = prefix ? `${prefix}/${name}` : name;
      if ((entry as any).file) {
        flat[path] = (entry as any).file.contents;
      } else if ((entry as any).directory) {
        Object.assign(flat, flattenFiles((entry as any).directory, path));
      }
    }
    return flat;
  };

  const getFileContent = (path: string, currentFiles: any): string => {
    if (!currentFiles) return '';
    const parts = path.split('/');
    let current = currentFiles;
    for (const part of parts) {
      if (!current[part]) return '';
      if (current[part]?.file) return current[part].file.contents;
      if (current[part]?.directory) current = current[part].directory;
    }
    return '';
  };

  // Initialize Workspace
  const loadBoilerplate = async (cid: string): Promise<FileTree> => {
    console.log("No draft found, loading boilerplate...");
    const challengeFiles = await fetchChallengeFiles(cid);
    if (Object.keys(challengeFiles).length > 0) {
      return unflattenFiles(challengeFiles);
    }
    // Fallback boilerplate
    return {
      'index.js': { file: { contents: '// Start coding here\n' } },
      'package.json': { file: { contents: JSON.stringify({ name: "challenge", type: "module" }, null, 2) } }
    };
  };

  const finalizeFiles = (initialFiles: FileTree) => {
    lastSavedHashRef.current = hashFiles(flattenFiles(initialFiles));
    setFiles(initialFiles);
    setIsBooting(false);

    if (initialFiles['README.md']) setSelectedFile('README.md');
    else if (initialFiles['index.ts']) setSelectedFile('index.ts');
    else if (initialFiles['index.js']) setSelectedFile('index.js');
  };

  useEffect(() => {
    async function init() {
      if (!challengeId || !user) return;

      setBootError(null);
      setIsBooting(true);
      setPendingDraft(null);
      setViewingSubmission(null);

      try {
        // 1. Fetch Challenge Metadata (fast DB read, no S3) and check for a draft in parallel
        const [meta, draftData] = await Promise.all([
          fetchChallenge(challengeId),
          fetchDraft(challengeId, user.id),
        ]);
        setChallengeMeta(meta);

        // Fire-and-forget, started as soon as the challenge is known valid — starts the
        // Fargate sandbox now so its ~30-60s cold start happens while the user reads the
        // problem or decides whether to resume a draft, not when they click Run. A failed
        // load above must never trigger this.
        // Note: the backend accepts this with a 202 almost immediately and boots the
        // container in the background, so its resolution does NOT mean the container is
        // actually running yet — don't treat it as a readiness signal.
        openWorkspaceSession(challengeId).catch((err) =>
          console.warn('Failed to open workspace session (will spawn lazily on Run instead):', err)
        );

        // Honest about what's actually true right now: the environment is still booting in
        // the background (can take ~30-60s). Run Tests works either way — it just waits for
        // the container if it's clicked before boot finishes — but claiming "ready" here was
        // misleading and made an early Run look like it was hanging for no reason.
        terminalInstanceRef.current?.write('\r\n\x1b[36m➤ Preparing your execution environment in the background — you can start coding now. "Run Tests" will wait for it if it\'s not ready yet.\x1b[0m\r\n');

        // 2. If a draft exists, let the user choose to continue or start over instead of
        // silently loading it — stop here and render the choice dialog.
        if (draftData) {
          setPendingDraft(draftData);
          setIsBooting(false);
          return;
        }

        // 3. No draft — go straight to boilerplate, default timer.
        setTimeLeft(3600);
        deadlineRef.current = Date.now() + 3600 * 1000;
        finalizeFiles(await loadBoilerplate(challengeId));
      } catch (err) {
        console.error("Failed to boot IDE", err);
        setBootError(err instanceof Error ? err.message : 'Failed to load this challenge.');
        setIsBooting(false);
      }
    }
    init();
  }, [challengeId, user, bootRetryKey]);

  const handleContinueDraft = () => {
    if (!pendingDraft) return;
    finalizeFiles(unflattenFiles(pendingDraft.files));
    const restoredTime = pendingDraft.pendingTime ?? 3600;
    setTimeLeft(restoredTime);
    deadlineRef.current = Date.now() + restoredTime * 1000;
    setPendingDraft(null);
  };

  const handleStartOver = async () => {
    if (!challengeId || !user) return;
    setPendingDraft(null);
    setIsBooting(true);
    try {
      await deleteDraft(challengeId, user.id);
      setTimeLeft(3600);
      deadlineRef.current = Date.now() + 3600 * 1000;
      finalizeFiles(await loadBoilerplate(challengeId));
    } catch (err) {
      console.error("Failed to start over", err);
      setBootError(err instanceof Error ? err.message : 'Failed to reset this challenge.');
      setIsBooting(false);
    }
  };

  // Handle terminal readiness
  useEffect(() => {
    if (terminal) {
      terminalInstanceRef.current = terminal;
    }
  }, [terminal]);

  // Kept in sync so persistDraftIfChanged() always reads the current countdown without
  // needing timeLeft (which ticks every second) in any effect's dependency array.
  useEffect(() => {
    timeLeftRef.current = timeLeft;
  }, [timeLeft]);

  // Shared by the debounced autosave below AND by Run/Submit (fired-and-forgotten there,
  // since the draft table is just "resume where you left off" — not on the grading path).
  const persistDraftIfChanged = async () => {
    if (!files || !challengeId || !user) return;
    // Locked files (tests/**, pom.xml, package.json, README.md) are given/read-only, not
    // user work — excluded from the draft entirely so they never factor into the change hash.
    const flatFiles = Object.fromEntries(
      Object.entries(flattenFiles(files)).filter(([path]) => !isLockedPath(path))
    );
    const currentHash = hashFiles(flatFiles);
    if (currentHash === lastSavedHashRef.current) {
      return; // No actual change since the last save — skip the network round-trip.
    }
    try {
      await saveDraft(challengeId, user.id, flatFiles, timeLeftRef.current);
      lastSavedHashRef.current = currentHash;
      console.log("Draft saved");
    } catch (err) {
      console.error("Draft save failed", err);
    }
  };

  // Debounced Auto-Save
  useEffect(() => {
    if (!files || !challengeId || !user) return;

    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    saveTimeoutRef.current = setTimeout(persistDraftIfChanged, 2000);

    return () => {
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    };
  }, [files, challengeId, user]);

  const handleRun = async () => {
    if (!challengeId || !files || isRunning) return;

    persistDraftIfChanged(); // Fire-and-forget — Run already sends files directly, this just checkpoints the draft.
    setIsRunning(true);
    setRunTestResults(null);
    if (terminal) {
      terminal.reset();
      terminal.write('\x1b[36m➤ Validating the code...\x1b[0m\r\n');
    }
    try {
      // Always runs server-side against the real Execution Service container — these are
      // Java/Maven challenges, which can't execute client-side in a browser.
      const result = await runChallenge(challengeId, flattenFiles(files));
      setRunTestResults(result.testResults ?? null);
      terminal?.write(result.stdout.replace(/\n/g, '\r\n'));
      if (result.stderr) terminal?.write(result.stderr.replace(/\n/g, '\r\n'));

      if (result.success) {
        terminal?.write('\r\n\x1b[32m✔ Tests passed!\x1b[0m\r\n');
      } else {
        terminal?.write(`\r\n\x1b[31m✘ Tests failed (Exit code: ${result.exitCode}).\x1b[0m\r\n`);
      }
    } catch (err) {
      console.error("Run failed", err);
      terminal?.write(`\r\n\x1b[31m✘ Execution error: ${err}\x1b[0m\r\n`);
    } finally {
      setIsRunning(false);
    }
  };

  const handleSubmit = async () => {
    if (!challengeId || !user || !files || isSubmitting) return;

    const confirmed = window.confirm("Are you sure you want to submit your solution? This will be graded.");
    if (!confirmed) return;

    persistDraftIfChanged(); // Fire-and-forget — checkpoints the draft separately from the submissions-table record below.
    setIsSubmitting(true);
    setSubmitStatus('Submitting...');
    try {
      // submitChallenge now blocks until the Execution Service finishes the test run
      // and returns the final result directly — no separate poll-for-result step.
      const submission = await submitChallenge({
        challengeId,
        files: flattenFiles(files),
        remainingTimeSeconds: timeLeft,
        userType: 'B2C'
      });

      setGradingResult(submission);
      setIsSubmitting(false);
      setSubmitStatus(submission.status === 'COMPLETED'
        ? `Grading complete! Score: ${submission.score}`
        : `Grading failed: ${submission.status}`);
      setSubmissionsRefreshKey((k) => k + 1); // New attempt just persisted server-side — refetch the history list.
    } catch (err) {
      console.error("Submission failed", err);
      setSubmitStatus('Submission failed');
      setIsSubmitting(false);
    }
  };

  const handleViewSubmission = async (submissionId: string) => {
    if (!challengeId) return;
    try {
      const detail = await fetchSubmissionDetail(challengeId, submissionId);
      setViewingSubmission(detail);
    } catch (err) {
      console.error("Failed to load submission", err);
    }
  };

  const handleBack = () => {
    const confirmed = window.confirm("Are you sure you want to go back to the dashboard? Unsaved changes may be lost (though we auto-save every 2s).");
    if (confirmed) {
      navigate('/problems');
    }
  };

  const handleReset = async () => {
    if (!challengeId || !user || isBooting) return;

    const confirmed = window.confirm("Are you sure you want to reset your workspace? This will DELETE all your current work and reload the original boilerplate.");
    if (!confirmed) return;

    try {
      setIsBooting(true);
      await deleteDraft(challengeId, user.id);
      window.location.reload(); // Hard reload to ensure clean state
    } catch (err) {
      console.error("Failed to reset workspace", err);
      setIsBooting(false);
      alert("Failed to reset workspace. Please try again.");
    }
  };

  const updateFileContent = (path: string, content: string) => {
    setFiles((prev: any) => {
      const newFiles = JSON.parse(JSON.stringify(prev));
      const parts = path.split('/');
      let current = newFiles;
      for (let i = 0; i < parts.length; i++) {
        const part = parts[i];
        if (i === parts.length - 1) {
          current[part].file.contents = content;
        } else {
          current = current[part].directory;
        }
      }
      return newFiles;
    });
  };

  const handleEditorChange = useCallback((value: string | undefined) => {
    if (selectedFile) {
      updateFileContent(selectedFile, value || '');
    }
  }, [selectedFile]);

  const handleFileSelect = (path: string) => {
    setSelectedFile(path);
    setOpenFiles(prev => prev.includes(path) ? prev : [...prev, path]);
  };

  // Refreshes the outline whenever the selected file (or its content) changes — cheap for
  // the regex fallback; the Monaco TS-worker path is async but re-entrant-safe since each
  // call is independent and only the latest one's result is ever rendered.
  useEffect(() => {
    if (!selectedFile) {
      setSymbols([]);
      return;
    }
    const content = getFileContent(selectedFile, files);
    let cancelled = false;
    extractSymbols(selectedFile, content, monacoRef.current, editorRef.current?.getModel()).then(result => {
      if (!cancelled) setSymbols(result);
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedFile, files]);

  const jumpToSymbol = (line: number) => {
    const editor = editorRef.current;
    if (!editor) return;
    editor.revealLineInCenter(line);
    editor.setPosition({ lineNumber: line, column: 1 });
    editor.focus();
  };

  const handleFileClose = (path: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const next = openFiles.filter(f => f !== path);
    setOpenFiles(next);
    if (selectedFile === path) {
      setSelectedFile(next.length > 0 ? next[next.length - 1] : null);
    }
  };

  useEffect(() => {
    if (gradingResult) {
      setActivePanel('feedback');
    }
  }, [gradingResult]);

  if (bootError) {
    return (
      <div className="flex h-full items-center justify-center bg-background text-text-muted">
        <div className="flex flex-col items-center gap-4 max-w-md text-center">
          <AlertTriangle className="text-red-500" size={40} />
          <p className="text-text-main font-medium">Couldn't load this challenge</p>
          <p className="text-[13px]">{bootError}</p>
          <button
            onClick={() => setBootRetryKey((k) => k + 1)}
            className="flex items-center gap-2 px-4 py-2 rounded bg-primary text-white hover:opacity-90 transition-opacity"
          >
            <RotateCcw size={16} />
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (pendingDraft) {
    return (
      <DraftResumeDialog
        updatedAt={pendingDraft.updatedAt}
        onContinue={handleContinueDraft}
        onStartOver={handleStartOver}
      />
    );
  }

  if (isBooting) {
    return (
      <div className="flex h-full items-center justify-center bg-white">
        <div className="flex flex-col items-center gap-4">
          <RefreshCcw className="animate-spin text-black" size={40} />
          <p className="animate-pulse text-gray-500">Booting your environment...</p>
        </div>
      </div>
    );
  }

  const readmeContent = getFileContent('README.md', files);
  const displayedFiles = viewingSubmission ? unflattenFiles(viewingSubmission.files) : files;

  return (
    <div className="flex flex-col h-full overflow-hidden bg-background text-text-main">
      {/* Workspace Header — 3-column grid so the timer sits dead-center regardless of how
          wide the left/right clusters are. */}
      <div className="h-12 border-b border-border-main bg-background grid grid-cols-3 items-center px-3 shrink-0">
        <div className="flex items-center gap-2 justify-self-start">
          <button
            onClick={handleBack}
            className="p-1.5 rounded hover:bg-black/5 dark:hover:bg-white/5 text-text-muted transition-all mr-1 cursor-pointer"
            title="Back to Dashboard"
          >
            <ArrowLeft size={16} />
          </button>
        </div>

        <div className="flex items-center gap-1.5 px-3 py-1 bg-black/5 dark:bg-white/5 rounded border border-border-main justify-self-center">
          <Hourglass size={13} className={timeLeft < 300 ? 'text-red-500 animate-pulse' : 'text-primary'} />
          <span className={`text-[14px] leading-none ${timeLeft < 300 ? 'text-red-500 animate-pulse' : 'text-primary'}`}>
            {formatTime(timeLeft)}
          </span>
          {isB2C && (
            <div className="flex items-center gap-1 ml-2 border-l border-border-main pl-2">
              {timerState === 'RUNNING' ? (
                <button onClick={handlePauseTimer} className="p-0.5 rounded hover:bg-black/10 dark:hover:bg-white/10 text-text-muted cursor-pointer" title="Pause"><Pause size={12} /></button>
              ) : (
                <button onClick={handleResumeTimer} className="p-0.5 rounded hover:bg-black/10 dark:hover:bg-white/10 text-text-muted cursor-pointer" title="Resume"><Play size={12} /></button>
              )}
              <button onClick={handleRestartTimer} className="p-0.5 rounded hover:bg-black/10 dark:hover:bg-white/10 text-text-muted cursor-pointer" title="Restart Timer"><RotateCcw size={12} /></button>
              <button onClick={handleStopTimer} className="p-0.5 rounded hover:bg-black/10 dark:hover:bg-white/10 text-text-muted cursor-pointer" title="Stop Timer"><Square size={12} /></button>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 justify-self-end">
          <button
            onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
            className="p-1.5 rounded hover:bg-black/5 dark:hover:bg-white/5 text-text-muted transition-all cursor-pointer"
            title={theme === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
          >
            {theme === 'light' ? <Moon size={14} /> : <Sun size={14} />}
          </button>
          <button
            onClick={handleReset}
            disabled={isBooting}
            className="p-1.5 rounded hover:bg-black/5 dark:hover:bg-white/5 text-text-muted transition-all cursor-pointer"
            title="Reset to Boilerplate"
          >
            <RotateCcw size={14} />
          </button>
          <button
            onClick={handleRun}
            disabled={isRunning}
            title={isRunning ? 'Running...' : 'Run Tests'}
            className="w-8 h-8 rounded flex items-center justify-center bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10 transition-all disabled:opacity-50 cursor-pointer"
          >
            {isRunning
              ? <RefreshCcw size={14} className="animate-spin text-text-muted" />
              : <Play size={14} className="text-text-muted fill-text-muted" />}
          </button>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="flex items-center gap-1.5 bg-primary hover:bg-primary/90 text-[var(--on-accent)] text-[14px] px-3 py-1.5 rounded transition-all disabled:opacity-50 cursor-pointer"
          >
            <Send size={12} />
            {isSubmitting ? 'Submitting...' : 'Submit'}
          </button>
        </div>
      </div>

      <div className="flex-1 min-w-0 flex min-h-0 overflow-hidden">
        {/* Collapsed rail — shown when the whole side panel is collapsed. Keeps every tab
            visible as a vertical icon+label so picking one both reopens the panel and
            switches straight to it, instead of collapsing down to a single bare chevron. */}
        {!activePanel && (
          <div className="w-9 shrink-0 flex flex-col items-center border-r border-border-main bg-panel">
            <div className="flex flex-col items-center w-full pt-2">
              <CollapsedTab icon={LayoutGrid} label="Explorer" active={lastPanelRef.current === 'explorer'} onClick={() => selectPanel('explorer')} />
              <div className="w-4 h-px bg-border-main my-1" />
              <CollapsedTab icon={BookOpen} label="Description" active={lastPanelRef.current === 'problem'} onClick={() => selectPanel('problem')} />
              <div className="w-4 h-px bg-border-main my-1" />
              <CollapsedTab icon={History} label="Submissions" active={lastPanelRef.current === 'submissions'} onClick={() => selectPanel('submissions')} />
              {gradingResult && (
                <>
                  <div className="w-4 h-px bg-border-main my-1" />
                  <CollapsedTab icon={Sparkles} label="Feedback" active={lastPanelRef.current === 'feedback'} onClick={() => selectPanel('feedback')} />
                </>
              )}
            </div>
            <div className="flex-grow" />
            <button
              onClick={() => setActivePanel(lastPanelRef.current)}
              className="p-1.5 mb-2 rounded hover:bg-black/5 dark:hover:bg-white/10 text-text-muted transition-all cursor-pointer"
              title="Expand panel"
            >
              <ChevronRight size={14} />
            </button>
          </div>
        )}

        <Split
          className={`flex flex-1 min-w-0 min-h-0 workspace-split ${!activePanel ? 'no-gutter' : ''}`}
          sizes={activePanel ? [25, 75] : [0, 100]}
          minSize={activePanel ? [220, 480] : [0, 480]}
          gutterSize={activePanel ? 4 : 0}
        >
          {/* Side Panel — single container for Explorer / Description / Submissions / Feedback,
              switched via a top tab strip (LeetCode-style) instead of a side icon rail.
              min-w-0 keeps wide Description content (long lines/code blocks) from forcing this
              panel past its allotted share and squeezing the editor's tab bar off-screen. */}
          <div className={`flex flex-col bg-panel border-r border-border-main overflow-hidden min-h-0 min-w-0 ${!activePanel ? 'invisible' : ''}`}>
            {activePanel && (
              <>
                <div className="flex items-center justify-between border-b border-border-main shrink-0 bg-elevated">
                  <div className="flex items-center overflow-x-auto">
                    <PanelTab
                      icon={LayoutGrid}
                      label="Explorer"
                      active={activePanel === 'explorer'}
                      onClick={() => selectPanel('explorer')}
                    />
                    <PanelTab
                      icon={BookOpen}
                      label="Description"
                      active={activePanel === 'problem'}
                      onClick={() => selectPanel('problem')}
                    />
                    <PanelTab
                      icon={History}
                      label="Submissions"
                      active={activePanel === 'submissions'}
                      onClick={() => selectPanel('submissions')}
                    />
                    {gradingResult && (
                      <PanelTab
                        icon={Sparkles}
                        label="Feedback"
                        active={activePanel === 'feedback'}
                        pulse={activePanel !== 'feedback'}
                        onClick={() => selectPanel('feedback')}
                      />
                    )}
                  </div>
                  <button
                    onClick={() => setActivePanel(null)}
                    className="p-1.5 mr-1 rounded hover:bg-black/5 dark:hover:bg-white/5 text-text-muted transition-all shrink-0 cursor-pointer"
                    title="Collapse panel"
                  >
                    <ChevronLeft size={14} />
                  </button>
                </div>

                <div className="flex-grow overflow-hidden bg-background min-h-0">
                  {activePanel === 'explorer' && (
                    <FileExplorer
                      files={displayedFiles || {}}
                      selectedFile={selectedFile}
                      onSelect={handleFileSelect}
                    />
                  )}
                  {activePanel === 'problem' && (
                    <div className="h-full overflow-y-auto overflow-x-hidden p-4 prose dark:prose-invert prose-xs max-w-none scrollbar-thin selection:bg-primary/30">
                      <ReactMarkdown
                        components={{
                          h1: ({node, ...props}) => (
                            <>
                              <h1 {...props} />
                              {challengeMeta?.difficulty && (
                                <div className="flex items-center gap-2 mt-3 mb-6">
                                  {(() => {
                                    const diff = DIFFICULTY_STYLES[challengeMeta.difficulty.toUpperCase()] ?? DIFFICULTY_STYLES.EASY;
                                    return (
                                      <span
                                        className="text-[11px] font-bold px-2.5 py-1 rounded-full"
                                        style={{ color: diff.color, background: diff.bg }}
                                      >
                                        {diff.label}
                                      </span>
                                    );
                                  })()}
                                  <span className="flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-full bg-black/5 dark:bg-white/5 text-text-muted">
                                    <Tag size={11} />
                                    Topics
                                  </span>
                                </div>
                              )}
                            </>
                          )
                        }}
                      >{stripSection(readmeContent || challengeMeta?.description || 'No description provided.', 'How to Build and Run')}</ReactMarkdown>
                    </div>
                  )}
                  {activePanel === 'submissions' && (
                    <div className="h-full overflow-y-auto scrollbar-thin">
                      <SubmissionsList
                        challengeId={challengeId!}
                        refreshKey={submissionsRefreshKey}
                        onViewSubmission={handleViewSubmission}
                      />
                    </div>
                  )}
                  {activePanel === 'feedback' && gradingResult && (
                    <div className="flex flex-col h-full min-h-0">
                      <div className="flex-grow overflow-y-auto min-h-0 scrollbar-thin">
                        <FeedbackDisplay result={gradingResult} />
                      </div>
                      <div className="border-t border-border-main p-3 shrink-0 bg-panel">
                        <input
                          placeholder="Ask a follow-up question..."
                          className="w-full text-[12px] bg-background border border-border-main rounded-lg px-3 py-2 text-text-main placeholder:text-text-muted focus:outline-none focus:border-primary transition-colors"
                        />
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>

          {/* Editor + Terminal — vertical Split */}
            <div className="flex flex-col flex-1 min-w-0 min-h-0 relative overflow-hidden">
              <Split
                direction="vertical"
                sizes={showTerminal ? [70, 30] : [100, 0]}
                minSize={showTerminal ? [200, 100] : [0, 0]}
                gutterSize={showTerminal ? 4 : 0}
                className="flex flex-col h-full min-h-0 split-vertical workspace-split"
                onDragEnd={() => terminalHandleRef.current?.fit()}
              >
                {/* Editor Section */}
                <div className="flex flex-col min-h-0 bg-background overflow-hidden">
                  {viewingSubmission && (
                    <div className="flex items-center justify-between gap-2 px-3 py-1.5 bg-primary/10 border-b border-border-main text-[11px] shrink-0">
                      <span className="text-text-main">
                        Viewing submission from{' '}
                        <span className="font-medium">
                          {new Date(viewingSubmission.submittedAt).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}
                        </span>
                        {' '}— read-only
                      </span>
                      <button
                        onClick={() => setViewingSubmission(null)}
                        className="flex items-center gap-1 px-2 py-1 rounded border border-border-main text-text-main hover:bg-black/5 dark:hover:bg-white/5 transition-all font-bold uppercase text-[10px] shrink-0"
                      >
                        <X size={12} />
                        Back to My Code
                      </button>
                    </div>
                  )}
                  {/* Tab bar — VS Code style */}
                  <div className="flex items-center bg-elevated border-b border-border-main shrink-0">
                    <div className="flex overflow-x-auto flex-1 min-w-0">
                      {openFiles.length === 0 ? (
                        <span className="px-4 py-2 text-[14px] text-text-muted">Select a file</span>
                      ) : (
                        openFiles.map(file => {
                          const locked = isLockedPath(file);
                          return (
                            <button
                              key={file}
                              onClick={() => setSelectedFile(file)}
                              className={`flex items-center gap-2 px-4 py-1.5 text-[13px] font-mono border-r border-border-main shrink-0 transition-all group ${
                                selectedFile === file
                                  ? 'bg-background text-text-main border-t border-t-primary'
                                  : 'bg-elevated text-text-muted hover:bg-panel hover:text-text-main'
                              }`}
                            >
                              {file.split('/').pop()}
                              {locked && <Lock size={10} className="text-text-muted" />}
                              <span
                                role="button"
                                onClick={(e) => handleFileClose(file, e)}
                                className="opacity-0 group-hover:opacity-60 hover:!opacity-100 hover:text-text-main rounded px-0.5 hover:bg-black/5 dark:hover:bg-white/10 leading-none text-[13px] cursor-pointer"
                              >
                                ×
                              </span>
                            </button>
                          );
                        })
                      )}
                    </div>
                    <div className="flex items-center gap-1 px-2 shrink-0 border-l border-border-main">
                      <button
                        onClick={() => setShowOutline(v => !v)}
                        className={`p-1.5 rounded transition-all cursor-pointer ${showOutline ? 'text-primary bg-primary/10' : 'text-text-muted hover:bg-black/5 dark:hover:bg-white/5'}`}
                        title="Toggle method/outline navigator"
                      >
                        <ListTree size={14} />
                      </button>
                      <button
                        onClick={() => setWordWrap(w => (w === 'off' ? 'on' : 'off'))}
                        className={`p-1.5 rounded transition-all cursor-pointer ${wordWrap === 'on' ? 'text-primary bg-primary/10' : 'text-text-muted hover:bg-black/5 dark:hover:bg-white/5'}`}
                        title={wordWrap === 'on' ? 'Disable word wrap' : 'Enable word wrap'}
                      >
                        <WrapText size={14} />
                      </button>
                    </div>
                  </div>

                  {/* Outline strip — collapsible list of methods/symbols in the current file */}
                  {showOutline && (
                    <div className="flex items-center gap-1.5 px-3 py-1.5 border-b border-border-main bg-elevated overflow-x-auto shrink-0">
                      {symbols.length === 0 ? (
                        <span className="text-[10px] text-text-muted">No symbols found in this file.</span>
                      ) : (
                        symbols.map((s, i) => (
                          <button
                            key={`${s.name}-${i}`}
                            onClick={() => jumpToSymbol(s.line)}
                            className="text-[10px] font-mono text-text-muted hover:text-primary hover:bg-primary/10 px-2 py-0.5 rounded whitespace-nowrap transition-all"
                            title={`Line ${s.line}`}
                          >
                            {s.name}
                          </button>
                        ))
                      )}
                    </div>
                  )}

                  {/* Monaco Editor */}
                  <div className="flex-grow overflow-hidden relative">
                    {timeLeft === 0 && (
                      <div className="absolute top-0 left-0 right-0 z-10 flex items-center gap-2 px-3 py-1.5 bg-red-500/90 text-white text-[11px] font-bold">
                        <AlertTriangle size={13} />
                        Time's up — the editor is now read-only. You can still submit.
                      </div>
                    )}
                    <Editor
                      height="100%"
                      theme={theme === 'light' ? 'vs' : 'vs-dark'}
                      path={selectedFile || ''}
                      value={selectedFile ? getFileContent(selectedFile, displayedFiles) : ''}
                      onChange={handleEditorChange}
                      onMount={(editorInstance, monacoInstance) => {
                        editorRef.current = editorInstance;
                        monacoRef.current = monacoInstance;
                      }}
                      options={{
                        minimap: { enabled: false },
                        fontSize: 14,
                        padding: { top: timeLeft === 0 ? 32 : 12 },
                        smoothScrolling: true,
                        cursorSmoothCaretAnimation: 'on',
                        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                        lineNumbersMinChars: 3,
                        glyphMargin: false,
                        folding: true,
                        scrollBeyondLastLine: false,
                        automaticLayout: true,
                        renderLineHighlight: 'all',
                        wordWrap,
                        readOnly: !!viewingSubmission || timeLeft === 0 || (selectedFile ? isLockedPath(selectedFile) : false),
                        scrollbar: {
                          vertical: 'visible',
                          horizontal: 'visible',
                          useShadows: false,
                          verticalScrollbarSize: 10,
                          horizontalScrollbarSize: 10,
                          alwaysConsumeMouseWheel: true,
                        }
                      }}
                    />
                  </div>
                </div>

                {/* Terminal Section */}
                <div className={`terminal-container bg-background border-t border-border-main z-20 ${!showTerminal ? 'invisible' : ''}`}>
                  <div className="h-7 border-b border-border-main bg-panel flex items-center px-3 shrink-0 justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-[14px] text-text-main">Terminal</span>
                    </div>
                    <button
                      onClick={() => setShowTerminal(false)}
                      className="p-1 rounded hover:bg-black/5 dark:hover:bg-white/5 text-text-muted transition-all cursor-pointer"
                      title="Hide Terminal"
                    >
                      <ChevronDown size={14} />
                    </button>
                  </div>
                  <div className="flex-grow overflow-hidden flex flex-col min-h-0">
                    {runTestResults && runTestResults.length > 0 && (
                      <div className="shrink-0 max-h-[40%] overflow-y-auto border-b border-border-main p-2">
                        <TestResultsList results={runTestResults} />
                      </div>
                    )}
                    <div className="flex-grow p-1.5 overflow-hidden min-h-0">
                      <TerminalComponent onTerminalReady={setTerminal} active={showTerminal} ref={terminalHandleRef} />
                    </div>
                  </div>
                </div>
              </Split>

              {/* Floating Terminal Bar (only when hidden) */}
              {!showTerminal && (
                <div className="h-8 border-t border-border-main bg-panel flex items-center px-3 shrink-0 justify-between absolute bottom-0 left-0 right-0 z-20">
                  <div className="flex items-center gap-2">
                    <span className="text-[14px] text-text-main">Terminal</span>
                  </div>
                  <button
                    onClick={() => setShowTerminal(true)}
                    className="p-1 rounded hover:bg-black/5 dark:hover:bg-white/5 text-text-muted transition-all flex items-center gap-1 cursor-pointer"
                    title="Show Terminal"
                  >
                    <TerminalIcon size={12} />
                    <ChevronUp size={14} />
                  </button>
                </div>
              )}
            </div>
        </Split>
      </div>

      {/* Status footer — only takes up space when there's an actual submit result to show. */}
      {submitStatus && (
        <div className="h-7 border-t border-border-main bg-background flex items-center px-3 justify-end shrink-0">
          <div className="text-[10px] text-primary font-black uppercase tracking-wider flex items-center gap-1">
            {submitStatus}
          </div>
        </div>
      )}
    </div>
  );
}

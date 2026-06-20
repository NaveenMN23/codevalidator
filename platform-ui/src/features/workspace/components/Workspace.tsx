import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Editor from '@monaco-editor/react';
import JSZip from 'jszip';
import Split from 'react-split';
import ReactMarkdown from 'react-markdown';
import { TerminalComponent } from './Terminal';
import { FileExplorer } from './FileExplorer';
import { FeedbackDisplay } from './FeedbackDisplay';
import { getWebContainer, runCommand } from '../../../lib/webcontainer';
import {
  Play, Send, RefreshCcw, LayoutGrid,
  ArrowLeft, ChevronUp, ChevronDown, CircleDot, Terminal as TerminalIcon,
  RotateCcw, Sparkles, BookOpen, Sun, Moon, X
} from 'lucide-react';
import { useAppStore } from '../../../store';
import type { FileSystemTree } from '@webcontainer/api';
import { fetchChallenge, fetchDraft, saveDraft, submitChallenge, deleteDraft, fetchSubmission } from '../api';
import type { GradingResult } from '../workspace.types';
import './Workspace.css';

const MINIO_BASE = ''; // Proxied through Nginx /challenges/ → MinIO (avoids COEP cross-origin block)

export function Workspace() {
  const { challengeId } = useParams<{ challengeId: string }>();
  const navigate = useNavigate();
  const { user, theme, setTheme } = useAppStore();

  const [files, setFiles] = useState<FileSystemTree | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [openFiles, setOpenFiles] = useState<string[]>([]);
  const [webcontainer, setWebcontainer] = useState<any>(null);
  const [terminal, setTerminal] = useState<any>(null);
  const [isBooting, setIsBooting] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitStatus, setSubmitStatus] = useState<string | null>(null);
  const [gradingResult, setGradingResult] = useState<GradingResult | null>(null);
  const [challengeMeta, setChallengeMeta] = useState<any>(null);
  const [showExplorer, setShowExplorer] = useState(true);
  const [showTerminal, setShowTerminal] = useState(true);
  const [activeLeftTab, setActiveLeftTab] = useState<'problem' | 'feedback' | 'explorer'>('problem');
  const [isInstalling, setIsInstalling] = useState(false);
  const [installComplete, setInstallComplete] = useState(false);
  const [timeLeft, setTimeLeft] = useState(3600);

  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const terminalInstanceRef = useRef<any>(null);

  // Timer
  useEffect(() => {
    const timer = setInterval(() => {
      setTimeLeft((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const unflattenFiles = (flatFiles: Record<string, string>): FileSystemTree => {
    const tree: FileSystemTree = {};
    for (const [path, content] of Object.entries(flatFiles)) {
      const parts = path.split('/');
      let current: any = tree;
      for (let i = 0; i < parts.length; i++) {
        const part = parts[i];
        if (i === parts.length - 1) {
          current[part] = { file: { contents: content } };
        } else {
          if (!current[part]) current[part] = { directory: {} };
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

  const patchContent = (path: string, content: string): string => {
    let patched = content;
    if (path === 'src/db.ts' && patched.includes('better-sqlite3')) {
      patched = patched.replace(
        "import Database from 'better-sqlite3';",
        "import initSqlJs from 'sql.js';"
      );
      patched = patched.replace(
        "const db = new Database('database.db');",
        "// Initialize WASM SQLite\nconst SQL = await initSqlJs();\nconst db = new SQL.Database();"
      );
      patched = patched.replace("database: db,", "database: db as any,");
    }
    if (path === 'package.json' && patched.includes('better-sqlite3')) {
      patched = patched.replace('"better-sqlite3": "^11.3.0"', '"sql.js": "^1.10.3"');
      if (!patched.includes('"@types/sql.js"')) {
        patched = patched.replace('"@types/better-sqlite3": "^7.6.13"', '"@types/sql.js": "^1.4.9"');
      }
    }
    return patched;
  };

  // Initialize workspace
  useEffect(() => {
    async function init() {
      if (!challengeId || !user) return;
      try {
        const meta = await fetchChallenge(challengeId);
        setChallengeMeta(meta);

        const draftData = await fetchDraft(challengeId, user.id);
        let initialFiles: FileSystemTree | null = null;

        if (draftData) {
          const flatFiles = draftData as Record<string, string>;
          for (const key of Object.keys(flatFiles)) {
            flatFiles[key] = patchContent(key, flatFiles[key]);
          }
          initialFiles = unflattenFiles(flatFiles);
        }

        if (!initialFiles) {
          const zipUrl = `${MINIO_BASE}${meta.zipUrl}`;
          const zipResponse = await fetch(zipUrl);
          if (zipResponse.ok) {
            const arrayBuffer = await zipResponse.arrayBuffer();
            const jszip = await JSZip.loadAsync(arrayBuffer);
            initialFiles = {};
            for (const [path, file] of Object.entries(jszip.files)) {
              if (!file.dir) {
                let content = await file.async('string');
                content = patchContent(path, content);
                const parts = path.split('/');
                let current = initialFiles;
                for (let i = 0; i < parts.length; i++) {
                  const part = parts[i];
                  if (i === parts.length - 1) {
                    current[part] = { file: { contents: content } };
                  } else {
                    current[part] = current[part] || { directory: {} };
                    current = (current[part] as any).directory;
                  }
                }
              }
            }
          } else {
            initialFiles = {
              'index.js': { file: { contents: '// Start coding here\n' } },
              'package.json': { file: { contents: JSON.stringify({ name: "challenge", type: "module" }, null, 2) } }
            };
          }
        }

        const wc = await getWebContainer();
        await wc.mount(initialFiles as any);
        setFiles(initialFiles as FileSystemTree);
        setWebcontainer(wc);
        setIsBooting(false);

        // Set default open file
        let defaultFile: string | null = null;
        if (initialFiles['README.md']) defaultFile = 'README.md';
        else if (initialFiles['index.ts']) defaultFile = 'index.ts';
        else if (initialFiles['index.js']) defaultFile = 'index.js';

        if (defaultFile) {
          setSelectedFile(defaultFile);
          setOpenFiles([defaultFile]);
        }

        setIsInstalling(true);
        terminalInstanceRef.current?.write('\x1b[33m➤ Starting background installation...\x1b[0m\r\n');

        const installProcess = await wc.spawn('npm', ['install', '--no-audit', '--no-fund']);
        installProcess.output.pipeTo(new WritableStream({
          write(data) {
            if (terminalInstanceRef.current) terminalInstanceRef.current.write(data);
          }
        }));

        const exitCode = await installProcess.exit;
        setIsInstalling(false);
        setInstallComplete(exitCode === 0);
        if (exitCode === 0) {
          terminalInstanceRef.current?.write('\r\n\x1b[32m✔ Environment is ready! Click "Run Tests" to execute.\x1b[0m\r\n');
        } else {
          terminalInstanceRef.current?.write('\r\n\x1b[31m✘ Background installation failed.\x1b[0m\r\n');
        }
      } catch (err) {
        console.error("Failed to boot IDE", err);
      }
    }
    init();
  }, [challengeId, user]);

  useEffect(() => {
    if (terminal) {
      terminalInstanceRef.current = terminal;
      if (isInstalling) {
        terminal.write('\x1b[33m➤ Dependencies are currently installing in the background...\x1b[0m\r\n');
      }
    }
  }, [terminal, isInstalling]);

  // Debounced auto-save
  useEffect(() => {
    if (!files || !challengeId || !user) return;
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    saveTimeoutRef.current = setTimeout(async () => {
      try {
        await saveDraft(challengeId, user.id, flattenFiles(files));
      } catch (err) {
        console.error("Auto-save failed", err);
      }
    }, 2000);
    return () => {
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    };
  }, [files, challengeId, user]);

  const handleRun = async () => {
    if (!webcontainer || isRunning) return;
    if (isInstalling) {
      terminal?.write('\r\n\x1b[33m⚠ Still installing dependencies. Please wait...\x1b[0m\r\n');
      return;
    }
    setIsRunning(true);
    try {
      if (terminal) {
        terminal.reset();
        terminal.write('\x1b[36m➤ Executing code...\x1b[0m\r\n');
      }
      const onData = (data: string) => terminal?.write(data);
      if (!installComplete) {
        terminal?.write('\x1b[33m➤ Retrying npm install...\x1b[0m\r\n');
        const installExitCode = await runCommand(webcontainer, 'npm', ['install'], onData, terminal);
        if (installExitCode !== 0) {
          terminal?.write('\r\n\x1b[31m✘ Dependency installation failed.\x1b[0m\r\n');
          return;
        }
        setInstallComplete(true);
      }
      terminal?.write('\x1b[33m➤ Running tests (npm test)...\x1b[0m\r\n');
      const testExitCode = await runCommand(webcontainer, 'npm', ['test'], onData, terminal);
      if (testExitCode === 0) {
        terminal?.write('\r\n\x1b[32m✔ Tests passed!\x1b[0m\r\n');
      } else {
        terminal?.write(`\r\n\x1b[31m✘ Tests failed (Exit code: ${testExitCode}).\x1b[0m\r\n`);
      }
    } catch (err) {
      terminal?.write(`\r\n\x1b[31m✘ Execution error: ${err}\x1b[0m\r\n`);
    } finally {
      setIsRunning(false);
    }
  };

  const handleSubmit = async () => {
    if (!challengeId || !user || !files || isSubmitting) return;
    const confirmed = window.confirm("Are you sure you want to submit your solution? This will be graded.");
    if (!confirmed) return;
    setIsSubmitting(true);
    setSubmitStatus('Submitting...');
    try {
      const initialSubmission = await submitChallenge({
        userId: user.id,
        challengeId,
        files: flattenFiles(files),
        isPremium: (user as any).isPremium || true,
        remainingTimeSeconds: timeLeft,
        userType: 'B2C'
      });
      setGradingResult(initialSubmission);
      setSubmitStatus('Grading in progress...');

      const pollInterval = setInterval(async () => {
        try {
          const updatedSubmission = await fetchSubmission(initialSubmission.id);
          setGradingResult(updatedSubmission);
          if (updatedSubmission.status !== 'PENDING') {
            clearInterval(pollInterval);
            setIsSubmitting(false);
            setSubmitStatus(updatedSubmission.status === 'COMPLETED'
              ? `Score: ${updatedSubmission.score}`
              : `Failed: ${updatedSubmission.status}`);
          }
        } catch (err) {
          clearInterval(pollInterval);
          setIsSubmitting(false);
          setSubmitStatus('Error checking grading status');
        }
      }, 2000);
    } catch (err) {
      setSubmitStatus('Submission failed');
      setIsSubmitting(false);
    }
  };

  const handleBack = () => {
    const confirmed = window.confirm("Go back to the dashboard? We auto-save every 2s.");
    if (confirmed) navigate('/');
  };

  const handleReset = async () => {
    if (!challengeId || !user || isBooting) return;
    const confirmed = window.confirm("Reset workspace? This will DELETE your current work and reload the original boilerplate.");
    if (!confirmed) return;
    try {
      setIsBooting(true);
      await deleteDraft(challengeId, user.id);
      window.location.reload();
    } catch (err) {
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
      webcontainer?.fs.writeFile(path, content);
      return newFiles;
    });
  };

  const handleEditorChange = useCallback((value: string | undefined) => {
    if (selectedFile) updateFileContent(selectedFile, value || '');
  }, [selectedFile, webcontainer]);

  // Open a file as a tab
  const handleFileSelect = useCallback((path: string) => {
    setSelectedFile(path);
    setOpenFiles(prev => prev.includes(path) ? prev : [...prev, path]);
  }, []);

  // Close a file tab
  const handleCloseTab = useCallback((path: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setOpenFiles(prev => {
      const newOpen = prev.filter(f => f !== path);
      if (selectedFile === path) {
        setSelectedFile(newOpen[newOpen.length - 1] ?? null);
      }
      return newOpen;
    });
  }, [selectedFile]);

  // Switch to AI Feedback tab when grading result arrives
  useEffect(() => {
    if (gradingResult) setActiveLeftTab('feedback');
  }, [gradingResult]);

  if (isBooting) {
    return (
      <div className="flex h-full items-center justify-center bg-background text-text-muted">
        <div className="flex flex-col items-center gap-4">
          <RefreshCcw className="animate-spin text-primary" size={40} />
          <p className="animate-pulse">Booting your environment...</p>
        </div>
      </div>
    );
  }

  const readmeContent = getFileContent('README.md', files);

  return (
    <div className="flex flex-col h-full overflow-hidden bg-background text-text-main">
      {/* Header */}
      <div className="h-11 border-b border-border-main bg-background flex items-center justify-between px-3 shrink-0">
        <div className="flex items-center gap-2">
          <button
            onClick={handleBack}
            className="p-1.5 rounded hover:bg-black/5 dark:hover:bg-white/5 text-text-muted transition-all"
            title="Back to Dashboard"
          >
            <ArrowLeft size={16} />
          </button>
          <button
            onClick={() => setShowExplorer(!showExplorer)}
            className={`p-1.5 rounded transition-all ${
              showExplorer
                ? 'bg-background border border-border-main text-primary shadow-sm shadow-primary/5'
                : 'hover:bg-black/5 dark:hover:bg-white/5 text-text-muted border border-transparent'
            }`}
            title={showExplorer ? 'Hide Sidebar' : 'Show Sidebar'}
          >
            <LayoutGrid size={16} />
          </button>
          <div className="w-px h-4 bg-border-main mx-1" />
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded border border-border-main flex items-center justify-center text-primary text-xs font-bold bg-background">
              {challengeMeta?.difficulty?.[0]}
            </div>
            <div className="flex flex-col">
              <h2 className="text-[11px] font-semibold text-text-main leading-tight">{challengeMeta?.title}</h2>
              <span className="text-[9px] text-text-muted font-bold uppercase tracking-wider">{challengeMeta?.language}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Compact Run/Submit when sidebar is hidden */}
          {!showExplorer && (
            <>
              <button
                onClick={handleRun}
                disabled={isRunning}
                className="flex items-center gap-1.5 bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10 text-text-main text-[11px] font-bold px-3 py-1.5 rounded border border-border-main transition-all disabled:opacity-50"
              >
                <Play size={12} className={isRunning ? 'animate-pulse text-primary fill-primary' : 'text-primary fill-primary'} />
                {isRunning ? 'Running...' : 'Run'}
              </button>
              <button
                onClick={handleSubmit}
                disabled={isSubmitting}
                className="flex items-center gap-1.5 bg-primary hover:bg-primary/90 text-white text-[11px] font-bold px-3 py-1.5 rounded transition-all disabled:opacity-50 shadow-sm shadow-primary/20"
              >
                <Send size={12} />
                {isSubmitting ? 'Submitting...' : 'Submit'}
              </button>
            </>
          )}

          {/* Theme toggle */}
          <button
            onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
            className="p-1.5 rounded hover:bg-black/5 dark:hover:bg-white/5 text-text-muted transition-all"
            title={theme === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
          >
            {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
          </button>

          <div className="flex flex-col items-center px-3 py-1 bg-black/5 dark:bg-white/5 rounded border border-border-main">
            <span className="text-[9px] text-text-muted font-bold uppercase leading-none mb-0.5">Time</span>
            <span className={`text-xs font-mono font-bold leading-none ${timeLeft < 300 ? 'text-red-500 animate-pulse' : 'text-primary'}`}>
              {formatTime(timeLeft)}
            </span>
          </div>

          <button
            onClick={handleReset}
            disabled={isBooting}
            className="p-1.5 rounded hover:bg-black/5 dark:hover:bg-white/5 text-text-muted transition-all"
            title="Reset to Boilerplate"
          >
            <RotateCcw size={14} />
          </button>
        </div>
      </div>

      <div className="flex-grow flex min-h-0 overflow-hidden">
        <Split
          className="flex flex-grow min-h-0"
          sizes={showExplorer ? [28, 72] : [0, 100]}
          minSize={showExplorer ? [220, 400] : [0, 400]}
          gutterSize={showExplorer ? 2 : 0}
        >
          {/* Left Panel — 3 tabs at top, submit/run pinned at bottom */}
          <div className={`flex flex-col bg-panel border-r border-border-main overflow-hidden transition-all min-h-0 ${!showExplorer ? 'hidden' : ''}`}>

            {/* Tab bar */}
            <div className="flex shrink-0 border-b border-border-main bg-background">
              <button
                onClick={() => setActiveLeftTab('problem')}
                className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-[10px] font-bold uppercase tracking-wider transition-all border-b-2 ${
                  activeLeftTab === 'problem'
                    ? 'border-primary text-primary'
                    : 'border-transparent text-text-muted hover:text-text-main hover:bg-black/5 dark:hover:bg-white/5'
                }`}
              >
                <BookOpen size={11} />
                Problem
              </button>
              <button
                onClick={() => setActiveLeftTab('feedback')}
                className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-[10px] font-bold uppercase tracking-wider transition-all border-b-2 ${
                  activeLeftTab === 'feedback'
                    ? 'border-primary text-primary'
                    : 'border-transparent text-text-muted hover:text-text-main hover:bg-black/5 dark:hover:bg-white/5'
                }`}
              >
                <Sparkles size={11} />
                AI Feedback
                {gradingResult && activeLeftTab !== 'feedback' && (
                  <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse ml-0.5" />
                )}
              </button>
              <button
                onClick={() => setActiveLeftTab('explorer')}
                className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-[10px] font-bold uppercase tracking-wider transition-all border-b-2 ${
                  activeLeftTab === 'explorer'
                    ? 'border-primary text-primary'
                    : 'border-transparent text-text-muted hover:text-text-main hover:bg-black/5 dark:hover:bg-white/5'
                }`}
              >
                <LayoutGrid size={11} />
                Files
              </button>
            </div>

            {/* Tab content — scrollable, takes all remaining space */}
            <div className="flex-grow overflow-y-auto min-h-0 bg-background">
              {activeLeftTab === 'problem' && (
                <div className="h-full overflow-y-auto p-4 prose dark:prose-invert prose-xs max-w-none scrollbar-thin">
                  <ReactMarkdown>
                    {readmeContent || challengeMeta?.description || 'No description provided.'}
                  </ReactMarkdown>
                </div>
              )}

              {activeLeftTab === 'feedback' && (
                <div className="flex flex-col h-full min-h-0">
                  <div className="flex-grow overflow-y-auto min-h-0">
                    {gradingResult ? (
                      <FeedbackDisplay result={gradingResult} />
                    ) : (
                      <div className="p-6 text-center mt-4">
                        <Sparkles className="mx-auto text-text-muted mb-3 opacity-20" size={28} />
                        <p className="text-[11px] text-text-muted leading-relaxed">
                          Submit your solution to receive AI-powered feedback
                        </p>
                      </div>
                    )}
                  </div>
                  {/* Chat input — enabled after submission */}
                  <div className="border-t border-border-main p-3 shrink-0 bg-panel">
                    <input
                      placeholder={gradingResult ? 'Ask a follow-up question...' : 'Submit your code to get AI feedback'}
                      disabled={!gradingResult}
                      className="w-full text-xs bg-background border border-border-main rounded-lg px-3 py-2 text-text-main placeholder:text-text-muted disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:border-primary transition-colors"
                    />
                  </div>
                </div>
              )}

              {activeLeftTab === 'explorer' && (
                <FileExplorer
                  files={files || {}}
                  selectedFile={selectedFile}
                  onSelect={handleFileSelect}
                />
              )}
            </div>

            {/* Submit + Run — always visible at bottom */}
            <div className="px-4 py-3 border-t border-border-main bg-panel shrink-0 space-y-2">
              <button
                onClick={handleSubmit}
                disabled={isSubmitting}
                className="w-full bg-primary hover:bg-primary/90 text-white text-xs font-bold py-2.5 rounded-lg transition-all disabled:opacity-50 flex items-center justify-center gap-1.5 shadow-sm shadow-primary/20"
              >
                <Send size={12} />
                {isSubmitting ? 'Submitting...' : 'Submit Solution'}
              </button>
              <button
                onClick={handleRun}
                disabled={isRunning}
                className="w-full bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10 text-text-main text-xs font-semibold py-2 rounded-lg border border-border-main transition-all disabled:opacity-50 flex items-center justify-center gap-1.5"
              >
                <Play size={12} className={isRunning ? 'animate-pulse text-primary fill-primary' : 'text-primary fill-primary'} />
                {isRunning ? 'Running...' : 'Run Tests'}
              </button>
            </div>
          </div>

          {/* Right: Editor + Terminal */}
          <div className="flex flex-col min-w-0 bg-background min-h-0 relative overflow-hidden">
            <div className="flex-grow flex flex-col min-h-0 overflow-hidden">
              <Split
                direction="vertical"
                sizes={showTerminal ? [70, 30] : [100, 0]}
                minSize={showTerminal ? [200, 100] : [0, 0]}
                gutterSize={showTerminal ? 4 : 0}
                className="flex flex-col h-full min-h-0 split-vertical"
              >
                {/* Editor section */}
                <div className="relative flex flex-col min-h-0 bg-background overflow-hidden">
                  {/* Multi-file tab bar */}
                  {openFiles.length > 0 && (
                    <div className="flex items-center border-b border-border-main bg-panel overflow-x-auto shrink-0 scrollbar-thin" style={{ scrollbarWidth: 'none' }}>
                      {openFiles.map(file => {
                        const name = file.split('/').pop()!;
                        const isActive = file === selectedFile;
                        return (
                          <div
                            key={file}
                            onClick={() => setSelectedFile(file)}
                            className={`flex items-center gap-1.5 px-3 text-[11px] font-medium border-r border-border-main cursor-pointer whitespace-nowrap shrink-0 group transition-colors relative ${
                              isActive
                                ? 'bg-background text-text-main py-2'
                                : 'text-text-muted hover:text-text-main hover:bg-background/60 py-2'
                            }`}
                          >
                            {isActive && (
                              <span className="absolute top-0 left-0 right-0 h-0.5 bg-primary" />
                            )}
                            {name}
                            <button
                              onClick={(e) => handleCloseTab(file, e)}
                              className="opacity-0 group-hover:opacity-60 hover:!opacity-100 hover:text-red-400 transition-all rounded p-0.5 -mr-1"
                            >
                              <X size={10} />
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  <div className="flex-grow overflow-hidden relative">
                    <Editor
                      height="100%"
                      theme={theme === 'light' ? 'vs' : 'vs-dark'}
                      path={selectedFile || ''}
                      value={selectedFile ? getFileContent(selectedFile, files) : ''}
                      onChange={handleEditorChange}
                      options={{
                        minimap: { enabled: false },
                        fontSize: 13,
                        padding: { top: 12 },
                        smoothScrolling: true,
                        cursorSmoothCaretAnimation: 'on',
                        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                        lineNumbersMinChars: 3,
                        glyphMargin: false,
                        folding: true,
                        scrollBeyondLastLine: false,
                        automaticLayout: true,
                        renderLineHighlight: 'all',
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

                {/* Terminal */}
                <div className={`terminal-container bg-background border-t border-border-main z-20 ${!showTerminal ? 'hidden' : ''}`}>
                  <div className="h-7 border-b border-border-main bg-panel flex items-center px-3 shrink-0 justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-[9px] text-text-muted font-black uppercase tracking-widest">Terminal</span>
                      {isInstalling && (
                        <div className="flex items-center gap-1.5 animate-pulse">
                          <CircleDot size={8} className="text-primary" />
                          <span className="text-[8px] text-text-muted font-bold uppercase">Installing...</span>
                        </div>
                      )}
                    </div>
                    <button
                      onClick={() => setShowTerminal(false)}
                      className="p-1 rounded hover:bg-black/5 dark:hover:bg-white/5 text-text-muted transition-all"
                    >
                      <ChevronDown size={14} />
                    </button>
                  </div>
                  <div className="flex-grow p-1.5 overflow-hidden">
                    <TerminalComponent onTerminalReady={setTerminal} />
                  </div>
                </div>
              </Split>
            </div>

            {/* Floating terminal bar when hidden */}
            {!showTerminal && (
              <div className="h-8 border-t border-border-main bg-panel flex items-center px-3 shrink-0 justify-between absolute bottom-0 left-0 right-0 z-20">
                <span className="text-[9px] text-text-muted font-black uppercase tracking-widest">Terminal</span>
                <button
                  onClick={() => setShowTerminal(true)}
                  className="p-1 rounded hover:bg-black/5 dark:hover:bg-white/5 text-text-muted transition-all flex items-center gap-1"
                >
                  <TerminalIcon size={12} />
                  <ChevronUp size={14} />
                </button>
              </div>
            )}
          </div>
        </Split>
      </div>

      {/* Footer status bar */}
      <div className="h-6 border-t border-border-main bg-background flex items-center px-3 justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-[9px] font-bold text-text-muted">
            <div className={`w-1.5 h-1.5 rounded-full ${webcontainer ? 'bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.3)]' : 'bg-red-500'}`} />
            {webcontainer ? 'READY' : 'CONNECTING...'}
          </div>
          <div className="w-px h-2.5 bg-border-main" />
          <div className="text-[9px] text-text-muted font-mono uppercase">
            {isRunning ? 'EXECUTING...' : isInstalling ? 'INSTALLING...' : 'IDLE'}
          </div>
        </div>
        {submitStatus && (
          <div className="text-[9px] text-primary font-black uppercase tracking-wider">
            {submitStatus}
          </div>
        )}
      </div>
    </div>
  );
}

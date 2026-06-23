import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Editor from '@monaco-editor/react';
import Split from 'react-split';
import ReactMarkdown from 'react-markdown';
import { TerminalComponent } from './Terminal';
import { FileExplorer } from './FileExplorer';
import { FeedbackDisplay } from './FeedbackDisplay';
import { getWebContainer } from '../../../lib/webcontainer';
import { 
  Play, Send, RefreshCcw, LayoutGrid, BookOpen, 
  ArrowLeft, ChevronUp, ChevronDown, Terminal as TerminalIcon,
  RotateCcw, Sparkles
} from 'lucide-react';
import { useAppStore } from '../../../store';
import type { FileSystemTree } from '@webcontainer/api';
import { fetchChallenge, fetchDraft, saveDraft, submitChallenge, deleteDraft, runChallenge } from '../api';
import type { GradingResult } from '../workspace.types';
import './Workspace.css';

export function Workspace() {
  const { challengeId } = useParams<{ challengeId: string }>();
  const navigate = useNavigate();
  const { user, theme } = useAppStore();
  
  const [files, setFiles] = useState<FileSystemTree | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
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
  const [activeLeftTab, setActiveLeftTab] = useState<'problem' | 'explorer' | 'feedback'>('problem');
  const [timeLeft, setTimeLeft] = useState(3600); // 60 minutes default

  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const terminalInstanceRef = useRef<any>(null);

  // Timer logic
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

  const patchContent = (path: string, content: string): string => {
    let patched = content;
    // Fix SQLite Bindings by switching to WASM on the fly
    if (path === 'src/db.ts' && patched.includes('better-sqlite3')) {
      console.log("Hot-patching src/db.ts to use WASM SQLite...");
      patched = patched.replace(
        "import Database from 'better-sqlite3';", 
        "import initSqlJs from 'sql.js';"
      );
      patched = patched.replace(
        "const db = new Database('database.db');",
        "// Initialize WASM SQLite\nconst SQL = await initSqlJs();\nconst db = new SQL.Database();"
      );
      patched = patched.replace(
        "database: db,",
        "database: db as any,"
      );
    }
    if (path === 'package.json' && patched.includes('better-sqlite3')) {
      console.log("Hot-patching package.json to use WASM SQLite...");
      patched = patched.replace('"better-sqlite3": "^11.3.0"', '"sql.js": "^1.10.3"');
      if (!patched.includes('"@types/sql.js"')) {
        patched = patched.replace(
          '"@types/better-sqlite3": "^7.6.13"',
          '"@types/sql.js": "^1.4.9"'
        );
      }
    }
    return patched;
  };

  // Initialize Workspace
  useEffect(() => {
    async function init() {
      if (!challengeId || !user) return;
      
      try {
        // 1. Fetch Challenge Metadata
        const meta = await fetchChallenge(challengeId);
        setChallengeMeta(meta);

        // 2. Try fetching draft
        const draftData = await fetchDraft(challengeId, user.id);
        
        let initialFiles: FileSystemTree | null = null;

        // 3. If draft exists, unflatten it AND patch it
        if (draftData) {
          const flatFiles = draftData as Record<string, string>;
          // Auto-patch existing drafts too!
          for (const key of Object.keys(flatFiles)) {
            flatFiles[key] = patchContent(key, flatFiles[key]);
          }
          initialFiles = unflattenFiles(flatFiles);
        }

        // 4. If no draft, load boilerplate from the challenge's files
        if (!initialFiles) {
          console.log("No draft found, loading boilerplate...");
          if (meta.files && Object.keys(meta.files).length > 0) {
            const flatFiles: Record<string, string> = { ...meta.files };
            for (const key of Object.keys(flatFiles)) {
              flatFiles[key] = patchContent(key, flatFiles[key]);
            }
            initialFiles = unflattenFiles(flatFiles);
          } else {
            // Fallback boilerplate
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

        if (initialFiles['README.md']) setSelectedFile('README.md');
        else if (initialFiles['index.ts']) setSelectedFile('index.ts');
        else if (initialFiles['index.js']) setSelectedFile('index.js');

        terminalInstanceRef.current?.write('\r\n\x1b[32m✔ Environment is ready! Click "Run Tests" to execute.\x1b[0m\r\n');
      } catch (err) {
        console.error("Failed to boot IDE", err);
      }
    }
    init();
  }, [challengeId, user]);

  // Handle terminal readiness
  useEffect(() => {
    if (terminal) {
      terminalInstanceRef.current = terminal;
    }
  }, [terminal]);

  // Debounced Auto-Save
  useEffect(() => {
    if (!files || !challengeId || !user) return;

    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);

    saveTimeoutRef.current = setTimeout(async () => {
      try {
        await saveDraft(challengeId, user.id, flattenFiles(files));
        console.log("Draft auto-saved");
      } catch (err) {
        console.error("Auto-save failed", err);
      }
    }, 2000);

    return () => {
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    };
  }, [files, challengeId, user]);

  const handleRun = async () => {
    if (!challengeId || !files || isRunning) return;

    setIsRunning(true);
    if (terminal) {
      terminal.reset();
      terminal.write('\x1b[36m➤ Sending code to the Execution Service...\x1b[0m\r\n');
    }
    try {
      // Runs server-side against the real Execution Service container — WebContainers can
      // only run Node.js in-browser and can't execute a JVM/Maven project at all.
      const result = await runChallenge(challengeId, flattenFiles(files));
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
    } catch (err) {
      console.error("Submission failed", err);
      setSubmitStatus('Submission failed');
      setIsSubmitting(false);
    }
  };

  const handleBack = () => {
    const confirmed = window.confirm("Are you sure you want to go back to the dashboard? Unsaved changes may be lost (though we auto-save every 2s).");
    if (confirmed) {
      navigate('/');
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
      // Also update in WebContainer
      webcontainer?.fs.writeFile(path, content);
      return newFiles;
    });
  };

  const handleEditorChange = useCallback((value: string | undefined) => {
    if (selectedFile) {
      updateFileContent(selectedFile, value || '');
    }
  }, [selectedFile, webcontainer]);

  useEffect(() => {
    if (gradingResult) {
      setActiveLeftTab('feedback');
    }
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
      {/* Workspace Header - More compact */}
      <div className="h-11 border-b border-border-main bg-background flex items-center justify-between px-3 shrink-0">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <button 
              onClick={handleBack}
              className="p-1.5 rounded hover:bg-black/5 dark:hover:bg-white/5 text-text-muted transition-all mr-1"
              title="Back to Dashboard"
            >
              <ArrowLeft size={16} />
            </button>
            <div className="flex flex-col items-center px-3 py-1 bg-black/5 dark:bg-white/5 rounded border border-border-main mr-2">
              <span className="text-[9px] text-text-muted font-bold uppercase leading-none mb-0.5">Time Remaining</span>
              <span className={`text-xs font-mono font-bold leading-none ${timeLeft < 300 ? 'text-red-500 animate-pulse' : 'text-primary'}`}>
                {formatTime(timeLeft)}
              </span>
            </div>
            <button 
              onClick={() => setShowExplorer(!showExplorer)}
              className={`p-1.5 rounded transition-all ${showExplorer ? 'bg-background border border-border-main text-primary shadow-sm shadow-primary/5' : 'hover:bg-black/5 dark:hover:bg-white/5 text-text-muted border border-transparent'}`}
              title={showExplorer ? "Hide Sidebar" : "Show Sidebar"}
            >
              <LayoutGrid size={16} />
            </button>
            <div className="w-px h-4 bg-border-main ml-1" />
            <div className="flex items-center gap-2 ml-1">
              <div className="w-6 h-6 rounded border border-border-main flex items-center justify-center text-primary text-xs font-bold bg-background">
                {challengeMeta?.difficulty?.[0]}
              </div>
              <div className="flex flex-col">
                <h2 className="text-[11px] font-semibold text-text-main leading-tight">{challengeMeta?.title}</h2>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-[9px] text-text-muted font-bold uppercase tracking-wider">{challengeMeta?.language}</span>
                  <div className="w-1 h-1 rounded-full bg-border-main" />
                  <span className="text-[9px] text-text-muted font-medium uppercase">Node.js Framework</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button 
            onClick={handleReset}
            disabled={isBooting}
            className="p-1.5 rounded hover:bg-black/5 dark:hover:bg-white/5 text-text-muted transition-all mr-1"
            title="Reset to Boilerplate"
          >
            <RotateCcw size={14} />
          </button>
          <button 
            onClick={handleRun}
            disabled={isRunning}
            className="flex items-center gap-1.5 bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10 text-text-main text-[11px] font-bold px-3 py-1.5 rounded border border-border-main transition-all disabled:opacity-50"
          >
            <Play size={12} className={isRunning ? 'animate-pulse text-primary fill-primary' : 'text-primary fill-primary'} />
            {isRunning ? 'Running...' : 'Run Tests'}
          </button>
          <button 
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="flex items-center gap-1.5 bg-primary hover:bg-primary/90 text-white text-[11px] font-bold px-3 py-1.5 rounded transition-all disabled:opacity-50 shadow-lg shadow-primary/20"
          >
            <Send size={12} />
            {isSubmitting ? 'Submitting...' : 'Submit'}
          </button>
        </div>
      </div>

      <div className="flex-grow flex min-h-0 overflow-hidden">
        <Split 
          className="flex flex-grow min-h-0"
          sizes={showExplorer ? [25, 75] : [0, 100]}
          minSize={showExplorer ? [200, 400] : [0, 400]}
          gutterSize={showExplorer ? 2 : 0}
        >
          {/* Sidebar Area */}
          <div className={`flex flex-col bg-panel border-r border-border-main overflow-hidden transition-all min-h-0 ${!showExplorer ? 'hidden' : ''}`}>
            {/* Tabs - Smaller */}
            <div className="flex bg-background shrink-0 border-b border-border-main">
              <button 
                onClick={() => setActiveLeftTab('problem')}
                className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-[10px] font-bold uppercase tracking-wider transition-all border-b ${activeLeftTab === 'problem' ? 'border-primary text-primary bg-background' : 'border-transparent text-text-muted hover:text-text-main hover:bg-black/5 dark:hover:bg-white/5'}`}
              >
                <BookOpen size={12} />
                Problem
              </button>
              <button 
                onClick={() => setActiveLeftTab('explorer')}
                className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-[10px] font-bold uppercase tracking-wider transition-all border-b ${activeLeftTab === 'explorer' ? 'border-primary text-primary bg-background' : 'border-transparent text-text-muted hover:text-text-main hover:bg-black/5 dark:hover:bg-white/5'}`}
              >
                <LayoutGrid size={12} />
                Files
              </button>
              {gradingResult && (
                <button 
                  onClick={() => setActiveLeftTab('feedback')}
                  className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-[10px] font-bold uppercase tracking-wider transition-all border-b ${activeLeftTab === 'feedback' ? 'border-primary text-primary bg-background' : 'border-transparent text-primary hover:bg-primary/5 animate-pulse'}`}
                >
                  <Sparkles size={12} />
                  Feedback
                </button>
              )}
            </div>

            <div className="flex-grow overflow-hidden bg-background min-h-0">
              {activeLeftTab === 'problem' ? (
                <div className="h-full overflow-y-auto p-4 prose dark:prose-invert prose-xs max-w-none scrollbar-thin selection:bg-primary/30">
                  <ReactMarkdown>{readmeContent || challengeMeta?.description || 'No description provided.'}</ReactMarkdown>
                </div>
              ) : activeLeftTab === 'explorer' ? (
                <FileExplorer 
                  files={files || {}} 
                  selectedFile={selectedFile} 
                  onSelect={setSelectedFile} 
                />
              ) : (
                <div className="h-full overflow-y-auto p-4 scrollbar-thin">
                  <FeedbackDisplay result={gradingResult!} />
                </div>
              )}
            </div>
          </div>

          {/* Editor & Terminal Area */}
          <div className="flex flex-col min-w-0 bg-background min-h-0 relative overflow-hidden">
            <div className="flex-grow flex flex-col min-h-0 overflow-hidden">
              <Split 
                direction="vertical"
                sizes={showTerminal ? [70, 30] : [100, 0]}
                minSize={showTerminal ? [200, 100] : [0, 0]}
                gutterSize={showTerminal ? 4 : 0}
                className="flex flex-col h-full min-h-0 split-vertical"
              >
                {/* Editor Section */}
                <div className="relative flex flex-col min-h-0 bg-background overflow-hidden border-b border-border-main">
                  <div className="h-8 bg-panel border-b border-border-main flex items-center px-4 shrink-0 justify-between">
                    <span className="text-[10px] text-text-muted font-mono flex items-center gap-2">
                      {selectedFile || 'Select a file'}
                    </span>
                  </div>
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
                
                {/* Terminal Section */}
                <div className={`terminal-container bg-background border-t border-border-main z-20 ${!showTerminal ? 'hidden' : ''}`}>
                  <div className="h-7 border-b border-border-main bg-panel flex items-center px-3 shrink-0 justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-[9px] text-text-muted font-black uppercase tracking-widest">Terminal</span>
                    </div>
                    <button 
                      onClick={() => setShowTerminal(false)}
                      className="p-1 rounded hover:bg-black/5 dark:hover:bg-white/5 text-text-muted transition-all"
                      title="Hide Terminal"
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

            {/* Floating Terminal Bar (only when hidden) */}
            {!showTerminal && (
              <div className="h-8 border-t border-border-main bg-panel flex items-center px-3 shrink-0 justify-between absolute bottom-0 left-0 right-0 z-20">
                <div className="flex items-center gap-2">
                  <span className="text-[9px] text-text-muted font-black uppercase tracking-widest">Terminal</span>
                </div>
                <button 
                  onClick={() => setShowTerminal(true)}
                  className="p-1 rounded hover:bg-black/5 dark:hover:bg-white/5 text-text-muted transition-all flex items-center gap-1"
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

      {/* Footer - More compact */}
      <div className="h-6 border-t border-border-main bg-background flex items-center px-3 justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-[9px] font-bold text-text-muted">
            <div className={`w-1.5 h-1.5 rounded-full ${webcontainer ? 'bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.3)]' : 'bg-red-500'}`} />
            {webcontainer ? 'ENVIRONMENT READY' : 'CONNECTING...'}
          </div>
          <div className="w-px h-2.5 bg-border-main" />
          <div className="text-[9px] text-text-muted font-mono tracking-tighter uppercase">
            {isRunning ? 'EXECUTING...' : 'IDLE'}
          </div>
        </div>
        {submitStatus && (
          <div className="text-[9px] text-primary font-black uppercase tracking-wider flex items-center gap-1">
            {submitStatus}
          </div>
        )}
      </div>
    </div>
  );
}

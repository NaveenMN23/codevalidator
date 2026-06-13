import { useState, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import JSZip from 'jszip';
import { TerminalComponent } from './components/Terminal';
import { FileExplorer } from './components/FileExplorer';
import { getWebContainer, runCommand } from './lib/webcontainer';
import { Play, Send, CheckCircle, RefreshCcw } from 'lucide-react';
import './App.css';

const API_BASE = 'http://localhost:8080/api/main';
const MINIO_BASE = 'http://localhost:9000';
const TEST_USER_ID = '550e8400-e29b-41d4-a716-446655440000'; // Seeded in V2__seed_data.sql

function App() {
  const [files, setFiles] = useState<any>(null);
  const challengeId = 'book-my-show-beginner';
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [webcontainer, setWebcontainer] = useState<any>(null);
  const [terminal, setTerminal] = useState<any>(null);
  const [isBooting, setIsBooting] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitStatus, setSubmitStatus] = useState<string | null>(null);

  useEffect(() => {
    async function init() {
      try {
        // 1. Fetch Challenge Metadata to get zipUrl
        const metaResponse = await fetch(`${API_BASE}/challenges/${challengeId}`);
        const challengeMeta = await metaResponse.json();

        // 2. Fetch Draft from Backend
        const response = await fetch(`${API_BASE}/drafts/${challengeId}?userId=${TEST_USER_ID}`);
        
        let initialFiles = null;
        if (response.ok) {
           initialFiles = await response.json();
        }

        // 3. If no draft (404 or empty), fetch ZIP from MinIO
        if (!initialFiles || Object.keys(initialFiles).length === 0) {
           console.log("No draft found, fetching challenge ZIP from MinIO...");
           try {
             // The seeded zipUrl is like "/challenges/node/beginner-broken-refund.zip"
             // In MinIO, the bucket is "challenges", so the URL is http://localhost:9000 + zipUrl
             const zipUrl = `${MINIO_BASE}${challengeMeta.zipUrl}`;
             const zipResponse = await fetch(zipUrl);
             
             if (zipResponse.ok) {
               const arrayBuffer = await zipResponse.arrayBuffer();
               const jszip = await JSZip.loadAsync(arrayBuffer);
               initialFiles = {};
               
               for (const [path, file] of Object.entries(jszip.files)) {
                 if (!file.dir) {
                   const content = await file.async('string');
                   // Build the file tree structure for WebContainer
                   const parts = path.split('/');
                   let current = initialFiles;
                   for (let i = 0; i < parts.length; i++) {
                     const part = parts[i];
                     if (i === parts.length - 1) {
                       current[part] = { file: { contents: content } };
                     } else {
                       current[part] = current[part] || { directory: {} };
                       current = current[part].directory;
                     }
                   }
                 }
               }
               console.log("Successfully extracted challenge ZIP.");
               // Select the README by default
               if (initialFiles['README.md']) {
                 setSelectedFile('README.md');
               }
             } else {
               throw new Error(`Failed to fetch challenge ZIP: ${zipResponse.statusText}`);
             }
           } catch (e) {
             console.error("Failed to load ZIP, using fallback", e);
             initialFiles = {
              'index.js': { file: { contents: '// Start coding here\nconsole.log("Welcome to the challenge!");\n' } },
              'package.json': { file: { contents: JSON.stringify({ name: "challenge", type: "module", scripts: { test: "node index.js" } }, null, 2) } }
             };
           }
        }

        const wc = await getWebContainer();
        await wc.mount(initialFiles);
        
        setFiles(initialFiles);
        setWebcontainer(wc);
        setIsBooting(false);
      } catch (err) {
        console.error("Failed to boot IDE", err);
      }
    }
    init();
  }, [challengeId]);

  // Debounced Auto-save
  useEffect(() => {
    if (isBooting || !files) return;

    const timeout = setTimeout(async () => {
      console.log("Auto-saving draft...");
      await fetch(`${API_BASE}/drafts/${challengeId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId: TEST_USER_ID, files })
      });
    }, 2000);

    return () => clearTimeout(timeout);
  }, [files]);

  const handleFileSelect = (path: string) => {
    setSelectedFile(path);
  };

  const getFileContent = (path: string, nodes: any): string => {
    const parts = path.split('/');
    let current = nodes;
    for (const part of parts) {
      if (current[part]?.file) return current[part].file.contents;
      current = current[part]?.directory;
    }
    return '';
  };

  const updateFileContent = (path: string, content: string) => {
    const newFiles = { ...files };
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
    setFiles(newFiles);
    webcontainer?.fs.writeFile(path, content);
  };

  const handleRunCode = async () => {
    if (!webcontainer || !terminal || isRunning) return;
    
    setIsRunning(true);
    terminal.clear();
    terminal.writeln('Starting project (npm start)...\r\n');
    
    try {
        await runCommand(webcontainer, 'npm', ['start'], (data) => {
            terminal.write(data);
        });
    } finally {
        setIsRunning(false);
    }
  };

  const handleRunTests = async () => {
    if (!webcontainer || !terminal || isRunning) return;
    
    setIsRunning(true);
    terminal.clear();
    terminal.writeln('Running tests...\r\n');
    try {
        await runCommand(webcontainer, 'npm', ['test'], (data) => {
            terminal.write(data);
        });
    } finally {
        setIsRunning(false);
    }
  };

  const handleSubmit = async () => {
    if (isSubmitting) return;

    setIsSubmitting(true);
    setSubmitStatus('Submitting...');

    try {
      const response = await fetch(`${API_BASE}/submissions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          userId: TEST_USER_ID,
          challengeId: challengeId,
          files: files // Sending the full file map
        })
      });

      if (response.ok) {
        setSubmitStatus('Successfully submitted! Grading in progress.');
        setTimeout(() => setSubmitStatus(null), 5000);
      } else {
        throw new Error('Submission failed');
      }
    } catch (err) {
      console.error(err);
      setSubmitStatus('Error: Could not submit code.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isBooting) {
    return <div className="booting">Booting WebContainer...</div>;
  }

  return (
    <div className="ide-container">
      <div className="sidebar">
        <FileExplorer 
          files={files} 
          onFileSelect={handleFileSelect} 
          selectedFile={selectedFile} 
        />
      </div>
      <div className="main-content">
        <div className="toolbar">
          <div className="toolbar-left">
            <span className="file-path">{selectedFile || 'No file selected'}</span>
          </div>
          <div className="toolbar-right">
            {submitStatus && <span className="submit-status">{submitStatus}</span>}
            <button 
                className="toolbar-button run-btn" 
                onClick={handleRunCode} 
                disabled={isRunning}
            >
              {isRunning ? <RefreshCcw size={16} className="spin" /> : <Play size={16} />}
              Run
            </button>
            <button 
                className="toolbar-button test-btn" 
                onClick={handleRunTests} 
                disabled={isRunning}
            >
              <CheckCircle size={16} />
              Run Tests
            </button>
            <button 
                className="toolbar-button submit-btn" 
                onClick={handleSubmit} 
                disabled={isSubmitting}
            >
              <Send size={16} />
              {isSubmitting ? 'Submitting...' : 'Submit'}
            </button>
          </div>
        </div>
        <div className="editor-container">
          <Editor
            height="100%"
            theme="vs-dark"
            path={selectedFile || ''}
            value={selectedFile ? getFileContent(selectedFile, files) : ''}
            onChange={(value) => updateFileContent(selectedFile!, value || '')}
            options={{
              minimap: { enabled: false },
              fontSize: 14,
            }}
          />
        </div>
        <div className="terminal-container">
          <TerminalComponent onTerminalReady={setTerminal} />
        </div>
      </div>
    </div>
  );
}

export default App;

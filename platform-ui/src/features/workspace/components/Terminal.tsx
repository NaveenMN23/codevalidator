import { useEffect, useRef } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';

interface TerminalComponentProps {
  onTerminalReady: (terminal: Terminal) => void;
}

export function TerminalComponent({ onTerminalReady }: TerminalComponentProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);

  useEffect(() => {
    if (!terminalRef.current) return;

    const terminal = new Terminal({
      cursorBlink: true,
      theme: {
        background: '#09090b',
        foreground: '#e0e0e0',
        cursor: '#3b82f6',
        selectionBackground: 'rgba(255, 255, 255, 0.1)',
      },
      fontSize: 13,
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      allowTransparency: true,
    });
    
    const fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);
    
    terminal.open(terminalRef.current);
    fitAddon.fit();

    xtermRef.current = terminal;
    fitAddonRef.current = fitAddon;

    onTerminalReady(terminal);

    const resizeObserver = new ResizeObserver(() => {
      fitAddon.fit();
    });
    resizeObserver.observe(terminalRef.current);

    return () => {
      terminal.dispose();
      resizeObserver.disconnect();
    };
  }, []);

  return <div ref={terminalRef} className="h-full w-full overflow-hidden" />;
}

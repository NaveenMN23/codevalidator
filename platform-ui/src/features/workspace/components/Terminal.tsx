import { useEffect, useRef } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { useAppStore } from '../../../store';
import '@xterm/xterm/css/xterm.css';

interface TerminalComponentProps {
  onTerminalReady: (terminal: Terminal) => void;
}

export function TerminalComponent({ onTerminalReady }: TerminalComponentProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const theme = useAppStore(state => state.theme);

  useEffect(() => {
    if (!terminalRef.current) return;

    const terminal = new Terminal({
      cursorBlink: true,
      theme: theme === 'light' ? {
        background: '#ffffff',
        foreground: '#0f172a',
        cursor: '#3b82f6',
        selectionBackground: 'rgba(59, 130, 246, 0.2)',
      } : {
        background: '#09090b',
        foreground: '#e4e4e7',
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

  // Sync theme changes
  useEffect(() => {
    if (xtermRef.current) {
      xtermRef.current.options.theme = theme === 'light' ? {
        background: '#ffffff',
        foreground: '#0f172a',
        cursor: '#3b82f6',
        selectionBackground: 'rgba(59, 130, 246, 0.2)',
      } : {
        background: '#09090b',
        foreground: '#e4e4e7',
        cursor: '#3b82f6',
        selectionBackground: 'rgba(255, 255, 255, 0.1)',
      };
    }
  }, [theme]);

  return <div ref={terminalRef} className="h-full w-full overflow-hidden" />;
}

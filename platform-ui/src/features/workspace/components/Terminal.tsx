import { useEffect, useRef } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { useAppStore } from '../../../store';
import '@xterm/xterm/css/xterm.css';

interface TerminalComponentProps {
  onTerminalReady: (terminal: Terminal) => void;
}

function getTerminalTheme() {
  const s = getComputedStyle(document.documentElement);
  return {
    background: s.getPropertyValue('--bg-elevated').trim(),
    foreground: s.getPropertyValue('--text-main').trim(),
    cursor: s.getPropertyValue('--accent-color').trim(),
    selectionBackground: s.getPropertyValue('--terminal-selection-bg').trim(),
  };
}

export function TerminalComponent({ onTerminalReady }: TerminalComponentProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const theme = useAppStore(state => state.theme);

  useEffect(() => {
    if (!terminalRef.current) return;

    const terminal = new Terminal({
      cursorBlink: true,
      theme: getTerminalTheme(),
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

  useEffect(() => {
    if (xtermRef.current) {
      xtermRef.current.options.theme = getTerminalTheme();
    }
  }, [theme]);

  return <div ref={terminalRef} className="h-full w-full overflow-hidden" />;
}

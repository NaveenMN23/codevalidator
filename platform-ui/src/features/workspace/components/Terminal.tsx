import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { useAppStore } from '../../../store';
import '@xterm/xterm/css/xterm.css';

interface TerminalComponentProps {
  onTerminalReady: (terminal: Terminal) => void;
  // Whether the terminal pane is currently visible. FitAddon can't measure a 0-size /
  // just-shown container reliably from ResizeObserver alone, so we also force a fit()
  // right after this flips true (see Workspace.tsx's showTerminal toggle).
  active: boolean;
}

export interface TerminalHandle {
  fit: () => void;
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

export const TerminalComponent = forwardRef<TerminalHandle, TerminalComponentProps>(
  function TerminalComponent({ onTerminalReady, active }, ref) {
    const terminalRef = useRef<HTMLDivElement>(null);
    const xtermRef = useRef<Terminal | null>(null);
    const fitAddonRef = useRef<FitAddon | null>(null);
    const theme = useAppStore(state => state.theme);

    useImperativeHandle(ref, () => ({
      fit: () => fitAddonRef.current?.fit(),
    }));

    useEffect(() => {
      if (!terminalRef.current) return;

      const terminal = new Terminal({
        cursorBlink: true,
        theme: getTerminalTheme(),
        fontSize: 14,
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

    useEffect(() => {
      if (xtermRef.current) {
        xtermRef.current.options.theme = getTerminalTheme();
      }
    }, [theme]);

    useEffect(() => {
      if (!active) return;
      // The container was just given non-zero size again — ResizeObserver fires on the next
      // layout pass, but a rAF-delayed explicit fit is more reliable across browsers.
      const raf = requestAnimationFrame(() => fitAddonRef.current?.fit());
      return () => cancelAnimationFrame(raf);
    }, [active]);

    return <div ref={terminalRef} className="h-full w-full overflow-hidden" />;
  }
);

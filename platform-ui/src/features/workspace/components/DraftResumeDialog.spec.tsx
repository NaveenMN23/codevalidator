import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { DraftResumeDialog } from './DraftResumeDialog';

describe('DraftResumeDialog', () => {
  it('renders a formatted last-saved timestamp', () => {
    render(
      <DraftResumeDialog
        updatedAt="2026-07-20T10:30:00.000Z"
        onContinue={vi.fn()}
        onStartOver={vi.fn()}
      />
    );

    const expected = new Date('2026-07-20T10:30:00.000Z').toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    });
    expect(screen.getByText(expected)).toBeInTheDocument();
  });

  it('calls onContinue when "Continue Draft" is clicked', async () => {
    const onContinue = vi.fn();
    const user = userEvent.setup();
    render(
      <DraftResumeDialog updatedAt="2026-07-20T10:30:00.000Z" onContinue={onContinue} onStartOver={vi.fn()} />
    );

    await user.click(screen.getByRole('button', { name: /continue draft/i }));

    expect(onContinue).toHaveBeenCalledTimes(1);
  });

  it('calls onStartOver when "Start Over" is clicked', async () => {
    const onStartOver = vi.fn();
    const user = userEvent.setup();
    render(
      <DraftResumeDialog updatedAt="2026-07-20T10:30:00.000Z" onContinue={vi.fn()} onStartOver={onStartOver} />
    );

    await user.click(screen.getByRole('button', { name: /start over/i }));

    expect(onStartOver).toHaveBeenCalledTimes(1);
  });

  it('does not call the other handler when one button is clicked', async () => {
    const onContinue = vi.fn();
    const onStartOver = vi.fn();
    const user = userEvent.setup();
    render(
      <DraftResumeDialog updatedAt="2026-07-20T10:30:00.000Z" onContinue={onContinue} onStartOver={onStartOver} />
    );

    await user.click(screen.getByRole('button', { name: /continue draft/i }));

    expect(onContinue).toHaveBeenCalledTimes(1);
    expect(onStartOver).not.toHaveBeenCalled();
  });
});

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { SubmissionsList } from './SubmissionsList';
import { fetchSubmissions } from '../api';
import type { SubmissionSummary } from '../workspace.types';

vi.mock('../api', () => ({
  fetchSubmissions: vi.fn(),
}));

const mockFetchSubmissions = vi.mocked(fetchSubmissions);

const SUBMISSIONS: SubmissionSummary[] = [
  { id: 'sub-1', status: 'COMPLETED', score: 100, submittedAt: '2026-07-20T10:30:00.000Z' },
  { id: 'sub-2', status: 'FAILED', score: 0, submittedAt: '2026-07-19T09:00:00.000Z' },
];

describe('SubmissionsList', () => {
  beforeEach(() => {
    mockFetchSubmissions.mockReset();
  });

  it('renders a row per submission with status and formatted timestamp', async () => {
    mockFetchSubmissions.mockResolvedValue(SUBMISSIONS);
    render(<SubmissionsList challengeId="c1" refreshKey={0} onViewSubmission={vi.fn()} />);

    expect(await screen.findByText('Accepted')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });

  it('shows an empty state when there are no submissions', async () => {
    mockFetchSubmissions.mockResolvedValue([]);
    render(<SubmissionsList challengeId="c1" refreshKey={0} onViewSubmission={vi.fn()} />);

    expect(await screen.findByText('No submissions yet.')).toBeInTheDocument();
  });

  it('calls onViewSubmission with the submission id when a row is clicked', async () => {
    mockFetchSubmissions.mockResolvedValue(SUBMISSIONS);
    const onViewSubmission = vi.fn();
    const user = userEvent.setup();
    render(<SubmissionsList challengeId="c1" refreshKey={0} onViewSubmission={onViewSubmission} />);

    const row = await screen.findByText('Accepted');
    await user.click(row);

    expect(onViewSubmission).toHaveBeenCalledWith('sub-1');
  });

  it('shows an error message when the fetch fails', async () => {
    mockFetchSubmissions.mockRejectedValue(new Error('network error'));
    render(<SubmissionsList challengeId="c1" refreshKey={0} onViewSubmission={vi.fn()} />);

    await waitFor(() => expect(screen.getByText('Failed to load submissions.')).toBeInTheDocument());
  });

  it('refetches when refreshKey changes', async () => {
    mockFetchSubmissions.mockResolvedValue(SUBMISSIONS);
    const { rerender } = render(<SubmissionsList challengeId="c1" refreshKey={0} onViewSubmission={vi.fn()} />);
    await screen.findByText('Accepted');
    expect(mockFetchSubmissions).toHaveBeenCalledTimes(1);

    rerender(<SubmissionsList challengeId="c1" refreshKey={1} onViewSubmission={vi.fn()} />);

    await waitFor(() => expect(mockFetchSubmissions).toHaveBeenCalledTimes(2));
  });
});

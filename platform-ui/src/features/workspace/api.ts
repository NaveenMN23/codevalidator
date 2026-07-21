import type { Challenge, SubmissionRequest, GradingResult, TestCaseResult, SubmissionSummary, SubmissionDetail } from './workspace.types';
import { useAppStore } from '../../store';

function getAuthHeaders(): Record<string, string> {
  const token = useAppStore.getState().user?.token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function fetchChallenges(): Promise<Challenge[]> {
  // Dashboard treats this as the full catalog (all client-side filtering/grouping) —
  // a plain fetch() defaults to the backend's Pageable default (size 20), silently
  // truncating the list once published problems exceed that. Request a size large
  // enough to cover the whole catalog in one call instead of building out pagination
  // for a list this small (dozens to low hundreds of problems).
  const response = await fetch('/api/v1/problems?size=500&sort=createdAt,desc');
  if (!response.ok) throw new Error('Failed to fetch challenges');
  const data = await response.json();
  // Backend returns PageResponse<ProblemSummaryResponse> — extract content array
  const items: any[] = Array.isArray(data) ? data : (data.content ?? []);
  return items.map((p: any): Challenge => ({
    id: p.id,
    slug: p.slug,
    title: p.title,
    difficulty: normalizeDifficulty(p.difficulty),
    language: p.language ?? (p.tags?.find((t: string) => ['node', 'java', 'python'].includes(t)) ?? 'node'),
    description: p.description,
  }));
}

export async function fetchChallenge(id: string): Promise<Challenge> {
  // Metadata only — fast DB read, no S3 involved. Use fetchChallengeFiles() separately
  // when the actual file contents are needed (skip it entirely if a draft exists).
  const response = await fetch(`/api/v1/problems/${id}`);
  if (!response.ok) throw new Error('Failed to fetch challenge');
  const p = await response.json();
  return {
    id: p.id,
    title: p.title,
    difficulty: normalizeDifficulty(p.difficulty),
    language: p.language ?? (p.tags?.find((t: string) => ['node', 'java', 'python'].includes(t)) ?? 'node'),
    description: p.description,
  };
}

export async function openWorkspaceSession(challengeId: string): Promise<void> {
  // Eagerly starts the Fargate sandbox for this problem so the cold start (~30-60s)
  // happens while the user is reading the brief, not when they click Run. Fire-and-forget:
  // the backend returns 202 immediately, callers should not await this for rendering.
  const response = await fetch(`/api/v1/problems/${challengeId}/run/session`, {
    method: 'POST',
    headers: { ...getAuthHeaders() },
  });
  if (!response.ok) throw new Error('Failed to open workspace session');
}

export async function fetchChallengeFiles(id: string): Promise<Record<string, string>> {
  const response = await fetch(`/api/v1/problems/${id}/files`);
  if (!response.ok) throw new Error('Failed to fetch challenge files');
  return response.json();
}

export interface DraftData {
  files: Record<string, string>;
  pendingTime: number | null;
  updatedAt: string;
}

export async function fetchDraft(challengeId: string, _userId: string): Promise<DraftData | null> {
  const response = await fetch(`/api/v1/drafts/${challengeId}`, {
    headers: { ...getAuthHeaders() },
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error('Failed to fetch draft');
  return response.json() as Promise<DraftData>;
}

export async function saveDraft(
  challengeId: string,
  _userId: string,
  files: Record<string, any>,
  pendingTime: number
): Promise<void> {
  const response = await fetch(`/api/v1/drafts/${challengeId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify({ files, pendingTime }),
  });
  if (!response.ok) throw new Error('Failed to save draft');
}

export async function deleteDraft(challengeId: string, _userId: string): Promise<void> {
  const response = await fetch(`/api/v1/drafts/${challengeId}`, {
    method: 'DELETE',
    headers: { ...getAuthHeaders() },
  });
  if (!response.ok) throw new Error('Failed to delete draft');
}

export interface RunResult {
  success: boolean;
  stdout: string;
  stderr: string;
  exitCode: number;
  testResults: TestCaseResult[];
}

export async function runChallenge(challengeId: string, files: Record<string, string>): Promise<RunResult> {
  // Runs the current file contents against the real Execution Service (the same Docker
  // container Submit uses) — code in WebContainers can't run a JVM/Maven project, so this
  // can't happen client-side for Java challenges.
  const response = await fetch(`/api/v1/problems/${challengeId}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify({ files }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.stderr || body?.detail || `HTTP ${response.status}`;
    throw new Error(detail);
  }
  return response.json();
}

export async function submitChallenge(payload: SubmissionRequest): Promise<GradingResult> {
  // Blocks until the Execution Service finishes the test run; the backend returns the
  // final result directly (no separate /submissions/{id} poll endpoint anymore).
  const response = await fetch(`/api/v1/problems/${payload.challengeId}/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify({
      files: payload.files,
      remainingTimeSeconds: payload.remainingTimeSeconds ?? 3600,
      userType: payload.userType ?? 'B2C',
    }),
  });
  if (!response.ok) throw new Error('Submission failed');
  return response.json();
}

export async function fetchSubmissions(challengeId: string): Promise<SubmissionSummary[]> {
  const response = await fetch(`/api/v1/problems/${challengeId}/submissions`, {
    headers: { ...getAuthHeaders() },
  });
  if (!response.ok) throw new Error('Failed to fetch submissions');
  return response.json();
}

export async function fetchSubmissionDetail(challengeId: string, submissionId: string): Promise<SubmissionDetail> {
  const response = await fetch(`/api/v1/problems/${challengeId}/submissions/${submissionId}`, {
    headers: { ...getAuthHeaders() },
  });
  if (!response.ok) throw new Error('Failed to fetch submission');
  return response.json();
}

function normalizeDifficulty(d: string): string {
  return d?.toUpperCase() ?? 'EASY';
}

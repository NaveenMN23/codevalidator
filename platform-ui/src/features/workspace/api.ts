import type { Challenge, SubmissionRequest, GradingResult } from './workspace.types';
import { useAppStore } from '../../store';

function getAuthHeaders(): Record<string, string> {
  const token = useAppStore.getState().user?.token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function fetchChallenges(): Promise<Challenge[]> {
  const response = await fetch('/api/v1/problems');
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
    zipUrl: p.zipUrl ?? `/api/v1/problems/${p.id}/zip`,
    description: p.description,
  }));
}

export async function fetchChallenge(id: string): Promise<Challenge> {
  const response = await fetch(`/api/v1/problems/${id}`);
  if (!response.ok) throw new Error('Failed to fetch challenge');
  const p = await response.json();
  return {
    id: p.id,
    title: p.title,
    difficulty: normalizeDifficulty(p.difficulty),
    language: p.language ?? (p.tags?.find((t: string) => ['node', 'java', 'python'].includes(t)) ?? 'node'),
    zipUrl: p.zipUrl ?? `/api/v1/problems/${p.id}/zip`,
    description: p.description,
  };
}

export async function fetchDraft(challengeId: string, _userId: string): Promise<Record<string, any> | null> {
  const response = await fetch(`/api/v1/drafts/${challengeId}`, {
    headers: { ...getAuthHeaders() },
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error('Failed to fetch draft');
  return response.json() as Promise<Record<string, any>>;
}

export async function saveDraft(challengeId: string, _userId: string, files: Record<string, any>): Promise<void> {
  const response = await fetch(`/api/v1/drafts/${challengeId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify({ files }),
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

export async function submitChallenge(payload: SubmissionRequest): Promise<GradingResult> {
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
  const data = await response.json();
  // Backend returns { id } with 202 — return a PENDING placeholder
  return { id: data.id, status: 'PENDING', score: null, logs: null };
}

export async function fetchSubmission(id: string): Promise<GradingResult> {
  const response = await fetch(`/api/v1/submissions/${id}`, {
    headers: { ...getAuthHeaders() },
  });
  if (!response.ok) throw new Error('Failed to fetch submission result');
  return response.json();
}

function normalizeDifficulty(d: string): string {
  return d?.toUpperCase() ?? 'EASY';
}

import type { Challenge, SubmissionRequest, GradingResult } from './workspace.types';

export async function fetchChallenges(): Promise<Challenge[]> {
  const response = await fetch('/api/main/challenges');
  if (!response.ok) throw new Error('Failed to fetch challenges');
  return response.json() as Promise<Challenge[]>;
}

export async function fetchChallenge(id: string): Promise<Challenge> {
  const response = await fetch(`/api/main/challenges/${id}`);
  if (!response.ok) throw new Error('Failed to fetch challenge');
  return response.json() as Promise<Challenge>;
}

export async function fetchDraft(challengeId: string, userId: string): Promise<Record<string, any> | null> {
  const response = await fetch(`/api/main/drafts/${challengeId}?userId=${userId}`);
  if (response.status === 404) return null;
  if (!response.ok) throw new Error('Failed to fetch draft');
  return response.json() as Promise<Record<string, any>>;
}

export async function saveDraft(challengeId: string, userId: string, files: Record<string, any>): Promise<void> {
  const response = await fetch(`/api/main/drafts/${challengeId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ userId, files }),
  });
  if (!response.ok) throw new Error('Failed to save draft');
}

export async function deleteDraft(challengeId: string, userId: string): Promise<void> {
  const response = await fetch(`/api/main/drafts/${challengeId}?userId=${userId}`, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error('Failed to delete draft');
}

export async function submitChallenge(payload: SubmissionRequest): Promise<GradingResult> {
  const response = await fetch('/api/main/submissions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error('Submission failed');
  return response.json();
}

export async function fetchSubmission(id: string): Promise<GradingResult> {
  const response = await fetch(`/api/main/submissions/${id}`);
  if (!response.ok) throw new Error('Failed to fetch submission result');
  return response.json();
}

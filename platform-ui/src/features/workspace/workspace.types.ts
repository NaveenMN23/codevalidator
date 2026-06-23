export interface Challenge {
  id: string;
  slug?: string;
  title: string;
  difficulty: string;
  language: string;
  files?: Record<string, string>;
  description?: string;
}

export interface ChallengeDraft {
  files: Record<string, string>;
}

export interface SubmissionRequest {
  challengeId: string;
  files: Record<string, string>;
  remainingTimeSeconds?: number;
  userType?: 'B2C' | 'B2B';
}

export interface GradingResult {
  id: string;
  status: 'COMPLETED' | 'FAILED';
  score: number | null;
  logs: string | null;
}

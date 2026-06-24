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
  status: 'PENDING' | 'COMPLETED' | 'FAILED' | 'TIMEOUT';
  score: number | null;
  logs: string | null;
  feedback?: {
    correctness: { finding: string; score: number };
    efficiency: { finding: string; score: number };
    followUp: { type: 'IMPLEMENTATION' | 'CONVERSATIONAL'; content: string };
    summary: string;
  };
}

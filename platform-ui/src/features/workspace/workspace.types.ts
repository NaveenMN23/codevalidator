export interface Challenge {
  id: string;
  title: string;
  difficulty: 'BEGINNER' | 'INTERMEDIATE' | 'ADVANCED';
  language: string;
  zipUrl: string;
}

export interface ChallengeDraft {
  files: Record<string, string>;
}

export interface SubmissionRequest {
  userId: string;
  challengeId: string;
  files: Record<string, string>;
  isPremium?: boolean;
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

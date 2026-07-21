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

export interface TestCaseResult {
  name: string;
  className: string;
  status: 'PASSED' | 'FAILED' | 'ERRORED' | 'SKIPPED';
  message: string | null;
  expected: string | null;
  actual: string | null;
  stackTrace: string | null;
}

export interface GradingResult {
  id: string;
  status: 'PENDING' | 'COMPLETED' | 'FAILED' | 'TIMEOUT';
  score: number | null;
  logs: string | null;
  testResults?: TestCaseResult[];
  feedback?: {
    correctness: { finding: string; score: number };
    efficiency: { finding: string; score: number };
    followUp: { type: 'IMPLEMENTATION' | 'CONVERSATIONAL'; content: string };
    summary: string;
  };
}

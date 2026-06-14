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
}

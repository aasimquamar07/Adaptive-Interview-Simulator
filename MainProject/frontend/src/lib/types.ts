export type Option = { value: string; label: string };

export interface Meta {
  demo_mode: boolean;
  provider: string;
  model: string | null;
  roles: Option[];
  interview_types: Option[];
  difficulties: Option[];
  durations: number[];
  languages: Option[];
}

export interface User { id: number; email: string; full_name: string; created_at: string | null }

export interface Question {
  id: number;
  seq: number;
  text: string;
  topic: string;
  topic_name: string;
  kind: string;
  level: number;
  level_label: string;
  hints_used: number;
  status: string;
  acknowledgement: string;
  why: string;
  source: string;
  strong_answer_covers?: string[];
}

export interface Evaluation {
  question_id: number;
  score: number;
  verdict: "correct" | "partial" | "incorrect" | "off_topic";
  correctness: number;
  relevance: number;
  depth: number;
  clarity: number;
  confidence: number;
  mastery_estimate: number;
  did_well: string;
  missing: string;
  improvement: string;
  missing_concepts: string[];
  held_back: boolean;
  evaluator: string;
  topic_name: string;
}

export interface TranscriptItem {
  question: Question;
  answer: { text: string; input_mode: string; response_seconds: number } | null;
  evaluation: Evaluation | null;
}

export interface SessionState {
  id: number;
  role: string;
  role_label: string;
  interview_type: string;
  difficulty_mode: string;
  current_level: number;
  level_label: string;
  duration_minutes: number;
  max_questions: number;
  language: "en" | "hi";
  mode: "text" | "voice";
  status: "active" | "completed";
  ai_provider: string;
  demo_mode: boolean;
  started_at: string;
  ends_at: string;
  remaining_seconds: number;
  question_number: number;
  answered_count: number;
  current_question: Question | null;
  transcript: TranscriptItem[];
  focus_topics: string[];
  skill_topics: string[];
  resume_skills: string[];
  overall_score: number | null;
  end_reason: string | null;
}

export interface StepResult {
  finished: boolean;
  reason: string | null;
  evaluation?: Evaluation | null;
  next_question: Question | null;
  session: SessionState;
}

export interface TopicPerf {
  topic: string; name: string; category: string; avg_score: number | null; questions: number; skipped: number;
  mastery_before: number | null; mastery_after: number | null; status: string; missed_concepts: string[];
}

export interface RoadmapItem {
  topic: string; name: string; priority: number; reason: string; actions: string[]; practice_questions: string[];
}

export interface Report {
  session_id: number;
  role: string;
  interview_type: string;
  overall_score: number | null;
  dimensions: Record<string, number | null>;
  objective: {
    questions_asked: number; answered: number; skipped: number; hints_used: number; repeats_requested: number;
    duration_seconds: number | null; avg_response_seconds: number | null; avg_answer_words: number | null;
    topics_covered: number; follow_ups_asked: number;
  };
  topics: TopicPerf[];
  strengths: string[];
  weaknesses: string[];
  ai_strengths?: string[];
  ai_weaknesses?: string[];
  needs_review: {
    seq: number; question: string; topic: string; answer: string; score: number; verdict: string;
    missing: string; improvement: string; strong_answer_covers: string[];
  }[];
  roadmap: RoadmapItem[];
  comparison: {
    sessions_compared: number; basis: string; previous_average: number | null; last_score: number | null;
    delta_vs_last: number | null; delta_vs_average: number | null; dimension_deltas: Record<string, number>;
    trend: { session_id: number; date: string | null; score: number | null; role: string; current?: boolean }[];
  };
  summary: string;
  summary_source: "ai" | "computed";
  disclaimer: string;
  evaluators: string[];
  ended_reason: string;
  extra_practice: { topic: string; question: string }[];
}

export interface MasteryRow {
  topic: string; name: string; category: string; mastery: number; label: string; attempts: number;
  correct: number; struggles: number; last_seen_at: string;
}

export interface Recommendation {
  id: number; topic: string; name: string; priority: number; reason: string; actions: string[];
  practice_questions: string[]; status: "open" | "done"; session_id: number | null; created_at: string;
}

export interface Overview {
  total_sessions: number;
  average_score: number | null;
  best_score: number | null;
  recent_average: number | null;
  previous_average: number | null;
  questions_answered: number;
  trend: ({ session_id: number; date: string; score: number; role: string } & Record<string, number | string>)[];
  mastery: MasteryRow[];
  weak_topics: MasteryRow[];
  strong_topics: MasteryRow[];
  active_session_id: number | null;
  top_recommendations: Recommendation[];
  recent_sessions: { id: number; role_label: string; interview_type: string; overall_score: number | null; status: string; started_at: string }[];
}

export interface HistoryRow {
  id: number; role_label: string; interview_type: string; difficulty_mode: string; status: string;
  overall_score: number | null; started_at: string; questions: number;
  dimensions: Record<string, number | null> | null; ai_provider: string;
}

export interface Profile {
  email: string; full_name: string; target_role: string; experience_level: string; preferred_language: "en" | "hi";
  resume_text: string; resume_skills: string[]; training_consent: boolean; training_consent_at: string | null;
}

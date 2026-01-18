export type PlatformKey = "tiktok" | "youtube" | "instagram" | "facebook";

export interface QueryRequest {
  question: string;
  platforms: PlatformKey[];
  use_llm?: boolean;
  llm_model?: string;
}

export interface Citation {
  page_title: string;
  section_heading: string;
  snippet: string;
  url: string;
}

export interface PlatformResult {
  answer: string;
  citations: Citation[];
}

export interface QueryResponse {
  question: string;
  platforms: Record<string, PlatformResult>;
  disclaimer: string;
}

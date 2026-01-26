import type { QueryRequest, QueryResponse } from "./types";

const API_URL = "http://127.0.0.1:8000/query";

export async function queryGraphRag(payload: QueryRequest): Promise<QueryResponse> {
  const finalPayload = {
    ...payload,
    use_llm: true,
    llm_model: "qwen2.5:3b-instruct"
  };
  const response = await fetch(API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(finalPayload)
  });

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }

  return response.json() as Promise<QueryResponse>;
}

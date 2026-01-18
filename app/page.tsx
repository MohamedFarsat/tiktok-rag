"use client";

import { useState } from "react";
import { PlatformSelector } from "../components/PlatformSelector";
import { AnswerCard } from "../components/AnswerCard";
import { Textarea } from "../components/ui/textarea";
import { Button } from "../components/ui/button";
import { Checkbox } from "../components/ui/checkbox";
import { queryGraphRag } from "../lib/api";
import type { PlatformKey, QueryResponse } from "../lib/types";

const DEFAULT_PLATFORMS: PlatformKey[] = ["tiktok", "youtube"];

export default function HomePage() {
  const [question, setQuestion] = useState("");
  const [platforms, setPlatforms] = useState<PlatformKey[]>(DEFAULT_PLATFORMS);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [useLlm, setUseLlm] = useState(true);

  const canSubmit = question.trim().length > 0 && platforms.length > 0 && !isLoading;

  const handleSubmit = async () => {
    if (!canSubmit) {
      return;
    }

    setErrorMessage(null);
    setIsLoading(true);

    try {
      const response = await queryGraphRag({
        question: question.trim(),
        platforms,
        use_llm: useLlm
      });
      setResult(response);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Unable to reach the backend."
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_#f6f2ea_0%,_#efe7dc_45%,_#e5ddd1_100%)] px-6 py-10">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-8">
        <header className="space-y-3">
          <p className="text-xs uppercase tracking-[0.4em] text-muted">Graph-RAG Demo</p>
          <h1 className="font-display text-3xl font-semibold text-ink md:text-4xl">
            Social Media Policy Assistant
          </h1>
          <p className="max-w-2xl text-sm text-muted md:text-base">
            Ask a question once and compare platform policy guidance with cited
            sources.
          </p>
        </header>

        <section className="space-y-4 rounded-3xl border border-line bg-white/80 p-6 shadow-soft backdrop-blur">
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-[0.3em] text-muted">Platforms</p>
            <PlatformSelector
              selected={platforms}
              onChange={setPlatforms}
              showWarning={platforms.length === 0}
            />
          </div>

          <div className="space-y-2">
            <p className="text-xs uppercase tracking-[0.3em] text-muted">Question</p>
            <Textarea
              placeholder="Ask a question about what content is allowed..."
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
            />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={handleSubmit} disabled={!canSubmit}>
              {isLoading ? (
                <>
                  <span className="mr-2 inline-flex h-4 w-4 items-center justify-center rounded-full border-2 border-white/40 border-t-white animate-spin" />
                  Asking...
                </>
              ) : (
                "Ask"
              )}
            </Button>
            <label className="flex items-center gap-2 text-sm text-muted">
              <Checkbox
                checked={useLlm}
                onCheckedChange={(checked) => setUseLlm(checked === true)}
              />
              Use LLM
            </label>
            {errorMessage ? (
              <p className="text-sm text-accent">{errorMessage}</p>
            ) : null}
          </div>
        </section>

        {result ? (
          <section className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-2xl text-ink">Results</h2>
              <p className="text-xs uppercase tracking-[0.2em] text-muted">
                {result.question}
              </p>
            </div>
            <div className="grid gap-6">
              {Object.entries(result.platforms).map(([platform, data]) => (
                <AnswerCard key={platform} platform={platform} result={data} />
              ))}
            </div>
          </section>
        ) : null}

        <footer className="rounded-3xl border border-line bg-white/70 p-6 text-sm text-muted shadow-soft">
          <p className="text-xs uppercase tracking-[0.3em] text-muted">Disclaimer</p>
          <p className="mt-2 text-sm text-ink">{result?.disclaimer ?? ""}</p>
        </footer>
      </div>
    </main>
  );
}

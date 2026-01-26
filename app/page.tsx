"use client";

import { useEffect, useRef, useState } from "react";
import { PlatformSelector } from "../components/PlatformSelector";
import { AnswerCard } from "../components/AnswerCard";
import { Textarea } from "../components/ui/textarea";
import { Button } from "../components/ui/button";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";
import { queryGraphRag } from "../lib/api";
import { cn } from "../lib/utils";
import type { PlatformKey, QueryResponse } from "../lib/types";

const DEFAULT_PLATFORMS: PlatformKey[] = ["tiktok", "youtube"];

export default function HomePage() {
  const [question, setQuestion] = useState("");
  const [platforms, setPlatforms] = useState<PlatformKey[]>(DEFAULT_PLATFORMS);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const {
    isSupported: isSpeechSupported,
    isListening,
    transcript,
    interimTranscript,
    error: speechError,
    start,
    stop,
    reset: resetSpeech
  } = useSpeechRecognition();

  const latestTranscriptRef = useRef("");
  const wasListeningRef = useRef(false);
  const canSubmit = question.trim().length > 0 && platforms.length > 0 && !isLoading;

  useEffect(() => {
    latestTranscriptRef.current = transcript;
  }, [transcript]);

  useEffect(() => {
    if (wasListeningRef.current && !isListening) {
      const finalTranscript = latestTranscriptRef.current.trim();
      if (finalTranscript) {
        setQuestion((prev) => {
          const trimmedPrev = prev.trim();
          if (!trimmedPrev) {
            return finalTranscript;
          }

          return `${trimmedPrev} ${finalTranscript}`.trim();
        });
      }

      resetSpeech();
    }

    wasListeningRef.current = isListening;
  }, [isListening, resetSpeech]);

  const handleSubmit = async () => {
    if (!canSubmit) {
      return;
    }

    setErrorMessage(null);
    setIsLoading(true);

    try {
      const response = await queryGraphRag({
        question: question.trim(),
        platforms
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
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs uppercase tracking-[0.3em] text-muted">Question</p>
              <Button
                type="button"
                onClick={isListening ? stop : start}
                disabled={!isSpeechSupported}
                aria-pressed={isListening}
                aria-label={isListening ? "Stop voice input" : "Start voice input"}
                className={cn(
                  "h-9 w-9 p-0",
                  isListening
                    ? "border-accent bg-accent text-white"
                    : "border-ink bg-ink text-white",
                  !isSpeechSupported && "cursor-not-allowed opacity-60"
                )}
              >
                {isListening ? <MicOffIcon className="h-4 w-4" /> : <MicIcon className="h-4 w-4" />}
              </Button>
            </div>
            <Textarea
              placeholder="Ask a question about what content is allowed..."
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
            />
            <div className="min-h-[20px] text-xs text-muted">
              {isListening ? (
                <span className="text-accent">Listening…</span>
              ) : null}
              {isListening && interimTranscript ? (
                <span className="ml-2 text-ink">{interimTranscript}</span>
              ) : null}
              {!isSpeechSupported ? (
                <span>Voice input is supported in Chrome/Edge.</span>
              ) : null}
              {isSpeechSupported && speechError ? (
                <span className="text-accent">{speechError}</span>
              ) : null}
            </div>
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

type IconProps = {
  className?: string;
};

const MicIcon = ({ className }: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <path d="M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
    <path d="M19 10v1a7 7 0 0 1-14 0v-1" />
    <path d="M12 18v4" />
    <path d="M8 22h8" />
  </svg>
);

const MicOffIcon = ({ className }: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <path d="M9 9v2a3 3 0 0 0 4.12 2.82" />
    <path d="M15 9V5a3 3 0 0 0-5.91-1.1" />
    <path d="M19 10v1a7 7 0 0 1-9.1 6.7" />
    <path d="M12 18v4" />
    <path d="M8 22h8" />
    <path d="M2 2l20 20" />
  </svg>
);

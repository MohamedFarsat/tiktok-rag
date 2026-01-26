"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type UseSpeechRecognitionOptions = {
  lang?: string;
};

type SpeechRecognitionCtor = new () => SpeechRecognition;

const getSpeechRecognitionCtor = (): SpeechRecognitionCtor | null => {
  if (typeof window === "undefined") {
    return null;
  }

  return (
    window.SpeechRecognition ||
    window.webkitSpeechRecognition ||
    null
  ) as SpeechRecognitionCtor | null;
};

const getErrorMessage = (error: string) => {
  switch (error) {
    case "not-allowed":
    case "service-not-allowed":
      return "Microphone permission was denied. Please allow access and try again.";
    case "no-speech":
      return "No speech was detected. Please try again.";
    case "audio-capture":
      return "No microphone was found.";
    case "network":
      return "Network error while using voice input. Please try again.";
    default:
      return "Voice input error. Please try again.";
  }
};

export const useSpeechRecognition = (options: UseSpeechRecognitionOptions = {}) => {
  const [isSupported, setIsSupported] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const finalTranscriptRef = useRef("");
  const langRef = useRef(options.lang ?? "en-US");

  useEffect(() => {
    langRef.current = options.lang ?? "en-US";
  }, [options.lang]);

  useEffect(() => {
    setIsSupported(Boolean(getSpeechRecognitionCtor()));

    return () => {
      recognitionRef.current?.abort();
      recognitionRef.current = null;
    };
  }, []);

  const reset = useCallback(() => {
    finalTranscriptRef.current = "";
    setTranscript("");
    setInterimTranscript("");
    setError(null);
  }, []);

  const start = useCallback(() => {
    const SpeechRecognition = getSpeechRecognitionCtor();
    if (!SpeechRecognition) {
      setIsSupported(false);
      setError("Voice input is supported in Chrome/Edge.");
      return;
    }

    if (!recognitionRef.current) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = langRef.current;

      recognition.onresult = (event: SpeechRecognitionEvent) => {
        let interimText = "";
        let finalText = "";

        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const result = event.results[i];
          const text = result[0]?.transcript ?? "";
          if (result.isFinal) {
            finalText += text;
          } else {
            interimText += text;
          }
        }

        if (finalText) {
          finalTranscriptRef.current += finalText;
          setTranscript(finalTranscriptRef.current);
        }

        setInterimTranscript(interimText);
      };

      recognition.onend = () => {
        setIsListening(false);
        setInterimTranscript("");
      };

      recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
        setError(getErrorMessage(event.error));
        setIsListening(false);
      };

      recognitionRef.current = recognition;
    } else {
      recognitionRef.current.lang = langRef.current;
    }

    reset();
    setError(null);

    try {
      recognitionRef.current.start();
      setIsListening(true);
    } catch (startError) {
      setIsListening(false);
      setError(
        startError instanceof Error
          ? startError.message
          : "Unable to start voice input."
      );
    }
  }, [reset]);

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
  }, []);

  return {
    isSupported,
    isListening,
    transcript,
    interimTranscript,
    error,
    start,
    stop,
    reset
  };
};

declare global {
  interface Window {
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  }
}

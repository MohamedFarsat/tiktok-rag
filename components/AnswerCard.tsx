import { Card } from "./ui/card";
import type { PlatformResult } from "../lib/types";
import { CitationsAccordion } from "./CitationsAccordion";

interface AnswerCardProps {
  platform: string;
  result: PlatformResult;
}

export function AnswerCard({ platform, result }: AnswerCardProps) {
  return (
    <Card className="space-y-4">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-muted">Platform</p>
        <h3 className="text-lg font-semibold text-ink">{platform}</h3>
      </div>
      <p className="text-sm leading-relaxed text-ink">{result.answer}</p>
      <div className="space-y-2">
        <p className="text-xs uppercase tracking-[0.2em] text-muted">Citations</p>
        <CitationsAccordion citations={result.citations} />
      </div>
    </Card>
  );
}

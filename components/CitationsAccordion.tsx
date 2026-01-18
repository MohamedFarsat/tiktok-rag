import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "./ui/accordion";
import type { Citation } from "../lib/types";

interface CitationsAccordionProps {
  citations: Citation[];
}

export function CitationsAccordion({ citations }: CitationsAccordionProps) {
  if (citations.length === 0) {
    return (
      <div className="rounded-2xl border border-line bg-white px-4 py-3 text-sm text-muted">
        No citations returned for this platform.
      </div>
    );
  }

  return (
    <Accordion type="single" collapsible className="space-y-3">
      {citations.map((citation, index) => (
        <AccordionItem value={`citation-${index}`} key={`${citation.url}-${index}`}>
          <AccordionTrigger>
            <span>
              {citation.page_title || "Untitled source"}{" "}
              <span className="text-xs text-muted">({citation.section_heading})</span>
            </span>
          </AccordionTrigger>
          <AccordionContent className="space-y-2">
            <p className="text-xs uppercase tracking-wide text-muted">Excerpt</p>
            <p className="text-sm text-ink">{citation.snippet}</p>
            <a
              className="text-sm font-semibold text-accent underline underline-offset-4"
              href={citation.url}
              target="_blank"
              rel="noreferrer"
            >
              Open source
            </a>
          </AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );
}

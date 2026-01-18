import * as React from "react";
import { cn } from "../../lib/utils";

const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "min-h-[160px] w-full rounded-2xl border border-line bg-white px-4 py-3 text-sm text-ink shadow-sm",
      "placeholder:text-muted focus:border-ink focus:outline-none focus:ring-2 focus:ring-ink/20",
      className
    )}
    {...props}
  />
));

Textarea.displayName = "Textarea";

export { Textarea };

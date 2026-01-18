import * as React from "react";
import { cn } from "../../lib/utils";

const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "rounded-3xl border border-line bg-white p-6 shadow-soft",
        className
      )}
      {...props}
    />
  )
);

Card.displayName = "Card";

export { Card };

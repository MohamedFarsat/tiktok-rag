import * as React from "react";
import { cn } from "../../lib/utils";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center rounded-full border border-ink bg-ink px-5 py-2 text-sm font-semibold text-white shadow-soft transition disabled:cursor-not-allowed disabled:opacity-60",
        "hover:bg-ink/90",
        className
      )}
      {...props}
    />
  )
);

Button.displayName = "Button";

export { Button };

import { InputHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "focus-ring w-full rounded-xl border border-white/10 bg-navy-800/60 px-4 py-2.5 text-cream placeholder:text-cream/30",
        "focus-visible:border-cyan-500/50",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";

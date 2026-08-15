import { cn } from "@/lib/utils";

export function ChatBubble({ role, children }: { role: "user" | "assistant"; children: React.ReactNode }) {
  const isUser = role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
          isUser ? "bg-cyan-500/15 text-cyan-50 rounded-br-sm" : "glass text-cream rounded-bl-sm"
        )}
      >
        {children}
      </div>
    </div>
  );
}

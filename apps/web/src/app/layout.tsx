import type { Metadata } from "next";
import "./globals.css";
import { ToastProvider } from "@/components/ui/Toast";

export const metadata: Metadata = {
  title: "LingoAdapt AI — An AI language tutor that adapts to how you actually learn.",
  description: "A personalized, agentic AI language-learning platform that remembers your mistakes, models how you learn, and adapts every lesson to you.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen font-sans antialiased">
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}

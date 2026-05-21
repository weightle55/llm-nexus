import "./globals.css";
import type { Metadata } from "next";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "llm-nexus",
  description: "Local LLM agent console",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

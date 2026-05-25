import "./globals.css";
import type { Metadata } from "next";
import { Providers } from "./providers";
import { themeBootstrapScript } from "@/lib/theme";

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
    <html lang="ko" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootstrapScript }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

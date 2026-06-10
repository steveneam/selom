import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import { MSWProvider } from "./msw-provider";

export const metadata: Metadata = {
  title: "Selom — no-code multi-omics figures",
  description:
    "Visualizing biology. Without code. Turn raw multi-omics data into publication-quality, editable figures.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="min-h-dvh bg-background font-sans text-foreground antialiased">
        <MSWProvider>{children}</MSWProvider>
      </body>
    </html>
  );
}

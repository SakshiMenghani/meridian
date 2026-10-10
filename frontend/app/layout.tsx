import type { Metadata } from "next";
import { DM_Sans, Fraunces } from "next/font/google";
import { Shell } from "@/components/shell";
import "./globals.css";

const sans = DM_Sans({ subsets: ["latin"], variable: "--font-dm-sans" });
const display = Fraunces({ subsets: ["latin"], variable: "--font-fraunces" });

export const metadata: Metadata = {
  title: "Meridian",
  description: "Connect databases and spreadsheets, then inspect them from one workspace.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${display.variable}`}>
      <body className="min-h-screen bg-paper font-sans text-ink antialiased">
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}

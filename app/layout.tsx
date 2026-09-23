import type { Metadata } from "next";
import { Onest, Unbounded } from "next/font/google";
import { LocaleSync } from "@/components/LocaleSync";
import "./globals.css";

const onest = Onest({ subsets: ["latin", "cyrillic", "cyrillic-ext"], variable: "--font-onest" });
const unbounded = Unbounded({ subsets: ["latin", "cyrillic"], weight: ["400", "500", "600"], variable: "--font-unbounded" });

export const metadata: Metadata = {
  title: "Career Quest",
  description: "Объяснимый навигатор развития сотрудника",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className={`${onest.variable} ${unbounded.variable}`}>
      <body><LocaleSync />{children}</body>
    </html>
  );
}

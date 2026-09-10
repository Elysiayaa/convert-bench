import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ConvertBench",
  description: "Format conversion agent with automatic failure dataset collection",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}


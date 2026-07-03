import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Agent Invest",
  description: "Multi-agent AI investment analysis system",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="th">
      <body className={inter.className}>
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 w-full min-w-0 overflow-x-hidden lg:ml-64 p-4 pt-20 lg:p-8">{children}</main>
        </div>
      </body>
    </html>
  );
}

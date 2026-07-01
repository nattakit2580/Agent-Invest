"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, Brain, Target, Download, Home, MessageCircle } from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: Home },
  { href: "/telegram", label: "Telegram Bot", icon: MessageCircle },
  { href: "/analyze", label: "เธงเธดเน€เธเธฃเธฒเธฐเธซเนเนเธซเธกเน", icon: Brain },
  { href: "/predictions", label: "เธเธฃเธฐเธงเธฑเธ•เธดเธเธฒเธฃเธเธฒเธ”เธเธฒเธฃเธ“เน", icon: Target },
  { href: "/accuracy", label: "เธเธงเธฒเธกเนเธกเนเธเธขเธณ", icon: BarChart3 },
  { href: "/export", label: "Export", icon: Download },
];

export default function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="fixed left-0 top-0 h-full w-64 bg-slate-900 border-r border-slate-700 flex flex-col">
      <div className="p-6 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <Brain className="w-7 h-7 text-sky-400" />
          <span className="text-xl font-bold text-white">Agent Invest</span>
        </div>
        <p className="text-xs text-slate-400 mt-1">Multi-Agent AI Analysis</p>
      </div>
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm transition-colors ${
                active
                  ? "bg-sky-600 text-white font-semibold"
                  : "text-slate-400 hover:bg-slate-800 hover:text-white"
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="p-4 border-t border-slate-700 text-xs text-slate-500 text-center">
        v1.0.0 ยท Agent Invest
      </div>
    </aside>
  );
}

"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, Brain, Target, Download, Home, MessageCircle, Settings, FlaskConical } from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: Home },
  { href: "/telegram", label: "Telegram Bot", icon: MessageCircle },
  { href: "/analyze", label: "วิเคราะห์หุ้น", icon: Brain },
  { href: "/predictions", label: "ประวัติการคาดการณ์", icon: Target },
  { href: "/accuracy", label: "ความแม่นยำ", icon: BarChart3 },
  { href: "/export", label: "Export", icon: Download },
  { href: "/admin", label: "Admin", icon: Settings },
  { href: "/deep-research", label: "Deep Research", icon: FlaskConical },
];

export default function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="fixed left-0 top-0 h-full w-64 bg-white border-r border-slate-200 flex flex-col">
      <div className="p-6 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <Brain className="w-7 h-7 text-blue-600" />
          <span className="text-xl font-bold text-slate-900">Agent Invest</span>
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
                  ? "bg-blue-50 text-blue-700 font-semibold"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="p-4 border-t border-slate-200 text-xs text-slate-400 text-center">
        v1.0.0 · Agent Invest
      </div>
    </aside>
  );
}

"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Brain,
  Target,
  Download,
  Home,
  MessageCircle,
  LineChart,
  CalendarClock,
  Sparkles,
  SlidersHorizontal,
  FlaskConical,
  Database,
  MessagesSquare,
  Menu,
  X,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: Home },
  { href: "/telegram", label: "Telegram Bot", icon: MessageCircle },
  { href: "/ai-chat", label: "AI Chat Feedback", icon: MessagesSquare },
  { href: "/analyze", label: "วิเคราะห์หุ้น", icon: Brain },
  { href: "/deep-research", label: "Deep Research", icon: FlaskConical },
  { href: "/predictions", label: "ประวัติการคาดการณ์", icon: Target },
  { href: "/accuracy", label: "ความแม่นยำ", icon: BarChart3 },
  { href: "/dataset", label: "Dataset", icon: Database },
  { href: "/economic", label: "ตัวเลขเศรษฐกิจ", icon: LineChart },
  { href: "/calendar", label: "ปฏิทินเหตุการณ์", icon: CalendarClock },
  { href: "/insights", label: "ระบบเรียนรู้", icon: Sparkles },
  { href: "/export", label: "Export", icon: Download },
  { href: "/admin", label: "Admin (โมเดล)", icon: SlidersHorizontal },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  // Close the mobile drawer whenever the route changes.
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  return (
    <>
      {/* Mobile top bar */}
      <header className="lg:hidden fixed top-0 left-0 right-0 h-14 bg-white border-b border-slate-200 flex items-center gap-3 px-4 z-20">
        <button
          onClick={() => setOpen(true)}
          aria-label="เปิดเมนู"
          className="text-slate-600 hover:text-slate-900 p-1 -ml-1"
        >
          <Menu className="w-6 h-6" />
        </button>
        <div className="flex items-center gap-2">
          <Brain className="w-6 h-6 text-blue-600" />
          <span className="text-lg font-bold text-slate-900">Agent Invest</span>
        </div>
      </header>

      {/* Mobile overlay */}
      {open && (
        <div
          onClick={() => setOpen(false)}
          className="lg:hidden fixed inset-0 bg-black/40 z-30"
          aria-hidden="true"
        />
      )}

      {/* Sidebar / drawer */}
      <aside
        className={`fixed left-0 top-0 h-full w-64 bg-white border-r border-slate-200 flex flex-col z-40 transform transition-transform duration-200 ease-out ${
          open ? "translate-x-0" : "-translate-x-full"
        } lg:translate-x-0`}
      >
        <div className="p-6 border-b border-slate-200 flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Brain className="w-7 h-7 text-blue-600" />
              <span className="text-xl font-bold text-slate-900">Agent Invest</span>
            </div>
            <p className="text-xs text-slate-400 mt-1">Multi-Agent AI Analysis</p>
          </div>
          <button
            onClick={() => setOpen(false)}
            aria-label="ปิดเมนู"
            className="lg:hidden text-slate-400 hover:text-slate-900 p-1"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {navItems.map(({ href, label, icon: Icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm transition-colors ${
                  active
                    ? "bg-blue-50 text-blue-700 font-semibold"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="p-4 border-t border-slate-200 text-xs text-slate-400 text-center">
          v1.0.0 · Agent Invest
        </div>
      </aside>
    </>
  );
}

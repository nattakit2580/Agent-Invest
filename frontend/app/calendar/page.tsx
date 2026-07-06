"use client";
import { useEffect, useState, useCallback } from "react";
import {
  CalendarClock,
  RefreshCw,
  TrendingUp,
  Coins,
  Rocket,
  BarChart2,
} from "lucide-react";
import { getCalendarEvents, refreshCalendar, type CalendarEvent } from "@/lib/api";

const RANGE_OPTIONS = [7, 14, 30, 60];

const TYPE_META: Record<
  string,
  { label: string; badge: string; Icon: React.ElementType; accent: string }
> = {
  earnings: {
    label: "งบการเงิน",
    badge: "bg-sky-900/50 text-sky-300 border border-sky-700",
    Icon: TrendingUp,
    accent: "bg-sky-500",
  },
  dividend: {
    label: "ปันผล",
    badge: "bg-emerald-900/50 text-emerald-300 border border-emerald-700",
    Icon: Coins,
    accent: "bg-emerald-500",
  },
  ipo: {
    label: "IPO",
    badge: "bg-purple-900/50 text-purple-300 border border-purple-700",
    Icon: Rocket,
    accent: "bg-purple-500",
  },
  economic: {
    label: "ตัวเลขเศรษฐกิจ",
    badge: "bg-amber-900/50 text-amber-300 border border-amber-700",
    Icon: BarChart2,
    accent: "bg-amber-500",
  },
};

function countdownChip(days: number) {
  let text: string;
  let cls: string;
  if (days <= 0) {
    text = "วันนี้";
    cls = "bg-red-500/20 text-red-300 border border-red-600/50";
  } else if (days === 1) {
    text = "พรุ่งนี้";
    cls = "bg-orange-500/20 text-orange-300 border border-orange-600/50";
  } else if (days <= 3) {
    text = `อีก ${days} วัน`;
    cls = "bg-amber-500/20 text-amber-300 border border-amber-600/50";
  } else {
    text = `อีก ${days} วัน`;
    cls = "bg-slate-700/60 text-slate-300 border border-slate-600";
  }
  return <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${cls}`}>{text}</span>;
}

function formatDateHeading(dateStr: string) {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("th-TH", { weekday: "long", day: "numeric", month: "long" });
}

export default function CalendarPage() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [range, setRange] = useState(30);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [autoRefreshed, setAutoRefreshed] = useState(false);

  const load = useCallback((days: number) => {
    setLoading(true);
    return getCalendarEvents(days)
      .then((res) => {
        setEvents(res.events);
        return res.events;
      })
      .finally(() => setLoading(false));
  }, []);

  const handleRefresh = useCallback(
    async (days: number) => {
      setRefreshing(true);
      try {
        await refreshCalendar();
        await load(days);
      } finally {
        setRefreshing(false);
      }
    },
    [load]
  );

  useEffect(() => {
    load(range).then((list) => {
      // First load with an empty DB (e.g. right after deploy): pull data once automatically.
      if (list && list.length === 0 && !autoRefreshed) {
        setAutoRefreshed(true);
        handleRefresh(range);
      }
    });
  }, [range, load, handleRefresh, autoRefreshed]);

  // group by date
  const grouped = events.reduce<Record<string, CalendarEvent[]>>((acc, ev) => {
    (acc[ev.event_date] ||= []).push(ev);
    return acc;
  }, {});
  const dates = Object.keys(grouped).sort();

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <CalendarClock className="w-8 h-8 text-sky-400" />
            ปฏิทินเหตุการณ์
          </h1>
          <p className="text-slate-400 mt-1">แจ้งเตือนล่วงหน้า: วันประกาศงบ · ปันผล · IPO</p>
        </div>
        <button
          onClick={() => handleRefresh(range)}
          disabled={refreshing}
          className="shrink-0 inline-flex items-center gap-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-2.5 rounded-lg transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
          รีเฟรช
        </button>
      </div>

      {/* range selector + legend */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="inline-flex bg-slate-800 border border-slate-700 rounded-lg p-1">
          {RANGE_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => setRange(d)}
              className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                range === d ? "bg-sky-600 text-white font-medium" : "text-slate-400 hover:text-white"
              }`}
            >
              {d} วัน
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          {Object.entries(TYPE_META).map(([key, m]) => (
            <span key={key} className="inline-flex items-center gap-1.5 text-xs text-slate-400">
              <span className={`w-2.5 h-2.5 rounded-full ${m.accent}`} />
              {m.label}
            </span>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-slate-800 border border-slate-700 rounded-xl h-20 animate-pulse" />
          ))}
        </div>
      ) : dates.length === 0 ? (
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-10 text-center text-slate-500">
          ไม่มีเหตุการณ์ในช่วง {range} วันข้างหน้า — กด &quot;รีเฟรช&quot; เพื่อดึงข้อมูลล่าสุด
        </div>
      ) : (
        <div className="space-y-6">
          {dates.map((date) => (
            <div key={date}>
              <div className="flex items-center gap-3 mb-3">
                <h2 className="text-sm font-semibold text-slate-300">{formatDateHeading(date)}</h2>
                <span className="text-xs text-slate-600 font-mono">{date}</span>
                <div className="flex-1 h-px bg-slate-800" />
              </div>
              <div className="space-y-2">
                {grouped[date].map((ev, i) => {
                  const meta = TYPE_META[ev.event_type] ?? TYPE_META.economic;
                  const Icon = meta.Icon;
                  return (
                    <div
                      key={`${ev.event_type}-${ev.symbol}-${i}`}
                      className="relative bg-slate-800 border border-slate-700 rounded-xl p-4 pl-5 flex items-center justify-between gap-4 hover:border-slate-600 transition-colors overflow-hidden"
                    >
                      <span className={`absolute left-0 top-0 h-full w-1 ${meta.accent}`} />
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="bg-slate-750 p-2 rounded-lg shrink-0">
                          <Icon className="w-4 h-4 text-slate-300" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            {ev.symbol && (
                              <span className="text-white font-semibold text-sm">{ev.symbol}</span>
                            )}
                            <span className={`text-[11px] px-2 py-0.5 rounded ${meta.badge}`}>
                              {meta.label}
                            </span>
                          </div>
                          <p className="text-slate-400 text-sm truncate mt-0.5">{ev.title}</p>
                        </div>
                      </div>
                      {countdownChip(ev.days_until)}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-slate-600 text-center pt-2">
        แหล่งข้อมูล: yfinance (งบ/ปันผล) · IPO watchlist · ตรวจสอบแหล่งข้อมูลหลักก่อนตัดสินใจลงทุน
      </p>
    </div>
  );
}

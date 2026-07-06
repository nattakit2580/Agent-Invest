"use client";
import { useEffect, useState, useCallback } from "react";
import { LineChart, RefreshCw, TrendingUp, TrendingDown, Minus, AlertCircle } from "lucide-react";
import {
  getEconomicIndicators,
  refreshEconomicIndicators,
  type EconomicIndicator,
} from "@/lib/api";

function fmtValue(v: number | null): string {
  if (v === null || v === undefined) return "—";
  const abs = Math.abs(v);
  if (abs >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
  if (abs >= 1) return v.toFixed(2);
  return v.toFixed(4);
}

function changeTone(change: number | null) {
  if (change === null || change === undefined || change === 0)
    return { color: "text-slate-400", Icon: Minus, ring: "border-slate-200" };
  if (change > 0) return { color: "text-emerald-600", Icon: TrendingUp, ring: "border-emerald-800/60" };
  return { color: "text-red-600", Icon: TrendingDown, ring: "border-red-800/60" };
}

function IndicatorCard({ item }: { item: EconomicIndicator }) {
  const { color, Icon, ring } = changeTone(item.change);
  return (
    <div className={`bg-white border ${ring} rounded-xl p-5 flex flex-col justify-between hover:border-slate-200 transition-colors`}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-slate-900 font-semibold leading-tight">{item.label}</p>
          <p className="text-[11px] text-slate-500 mt-0.5 font-mono">{item.series_id}</p>
        </div>
        <span className={`inline-flex items-center gap-1 text-xs font-medium ${color}`}>
          <Icon className="w-3.5 h-3.5" />
        </span>
      </div>

      <div className="mt-4">
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold text-slate-900">{fmtValue(item.value)}</span>
          {item.unit && <span className="text-xs text-slate-500">{item.unit}</span>}
        </div>
        <div className={`flex items-center gap-2 mt-1 text-sm ${color}`}>
          <span>
            {item.change !== null && item.change !== undefined
              ? `${item.change > 0 ? "+" : ""}${fmtValue(item.change)}`
              : "—"}
          </span>
          {item.change_pct !== null && item.change_pct !== undefined && (
            <span className="text-xs">
              ({item.change_pct > 0 ? "+" : ""}
              {item.change_pct.toFixed(2)}%)
            </span>
          )}
          <span className="text-slate-600 text-xs">vs prev</span>
        </div>
      </div>

      <div className="mt-4 pt-3 border-t border-slate-200/60 flex items-center justify-between text-[11px] text-slate-500">
        <span>อ้างอิง {item.observation_date ?? "—"}</span>
      </div>
    </div>
  );
}

export default function EconomicPage() {
  const [data, setData] = useState<EconomicIndicator[]>([]);
  const [configured, setConfigured] = useState(true);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    getEconomicIndicators()
      .then((res) => {
        setData(res.indicators);
        setConfigured(res.configured);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const res = await refreshEconomicIndicators();
      setData(res.indicators);
    } finally {
      setRefreshing(false);
    }
  };

  const lastUpdated = data.reduce<string | null>((acc, d) => {
    if (!d.updated_at) return acc;
    return !acc || d.updated_at > acc ? d.updated_at : acc;
  }, null);

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 flex items-center gap-3">
            <LineChart className="w-7 h-7 sm:w-8 sm:h-8 text-blue-600" />
            ตัวเลขเศรษฐกิจ
          </h1>
          <p className="text-slate-400 mt-1">
            ข้อมูลมหภาคจริงจาก FRED (Federal Reserve Economic Data)
            {lastUpdated && (
              <span className="text-slate-500 text-sm">
                {" "}· อัปเดตล่าสุด {new Date(lastUpdated).toLocaleString("th-TH")}
              </span>
            )}
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing || !configured}
          className="shrink-0 inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-2.5 rounded-lg transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
          รีเฟรชข้อมูล
        </button>
      </div>

      {!configured && (
        <div className="bg-amber-50 border border-amber-700/50 rounded-xl p-5 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="text-sm">
            <p className="text-amber-700 font-medium">ยังไม่ได้ตั้งค่า FRED API key</p>
            <p className="text-amber-700/70 mt-1">
              สมัครฟรีที่{" "}
              <a
                href="https://fredaccount.stlouisfed.org/apikeys"
                target="_blank"
                rel="noreferrer"
                className="underline hover:text-amber-100"
              >
                fredaccount.stlouisfed.org/apikeys
              </a>{" "}
              แล้วใส่ค่า <code className="bg-white px-1.5 py-0.5 rounded">FRED_API_KEY</code> ในไฟล์{" "}
              <code className="bg-white px-1.5 py-0.5 rounded">backend/.env</code>
            </p>
          </div>
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i} className="bg-white border border-slate-200 rounded-xl p-5 h-40 animate-pulse" />
          ))}
        </div>
      ) : data.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-xl p-10 text-center text-slate-500">
          ยังไม่มีข้อมูลตัวเลขเศรษฐกิจ — กด &quot;รีเฟรชข้อมูล&quot; เพื่อดึงจาก FRED
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.map((item) => (
            <IndicatorCard key={item.series_id} item={item} />
          ))}
        </div>
      )}

      <p className="text-xs text-slate-600 text-center pt-2">
        แหล่งข้อมูล: FRED · ตัวเลขเป็นข้อมูลอ้างอิง ไม่ใช่คำแนะนำการลงทุน
      </p>
    </div>
  );
}

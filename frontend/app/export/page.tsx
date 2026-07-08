"use client";
import { useState } from "react";
import { Download, FileSpreadsheet, FileText, Loader2 } from "lucide-react";

const API = "/api";

export default function ExportPage() {
  const [filter, setFilter] = useState({ symbol: "", timeframe: "", status: "" });
  const [downloading, setDownloading] = useState<"csv" | "excel" | null>(null);
  const [dlError, setDlError] = useState("");

  const buildUrl = (format: string) => {
    const params = new URLSearchParams();
    if (filter.symbol) params.append("symbol", filter.symbol.toUpperCase());
    if (filter.timeframe) params.append("timeframe", filter.timeframe);
    if (filter.status) params.append("status", filter.status);
    const qs = params.toString();
    return `${API}/export/${format}${qs ? "?" + qs : ""}`;
  };

  const handleDownload = async (format: "csv" | "excel") => {
    setDownloading(format);
    setDlError("");
    try {
      const res = await fetch(buildUrl(format));
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = format === "csv" ? "predictions.csv" : "predictions.xlsx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setDlError(e instanceof Error ? e.message : "ดาวน์โหลดไม่สำเร็จ");
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-3">
          <Download className="w-8 h-8 text-blue-600" />
          Export รายงาน
        </h1>
        <p className="text-slate-500 mt-1">ดาวน์โหลดผลการวิเคราะห์และความแม่นยำ</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6 space-y-5">
        <h2 className="text-slate-900 font-semibold">กรองข้อมูล (ไม่บังคับ)</h2>

        <div className="space-y-3">
          <div>
            <label className="text-slate-500 text-sm block mb-1">Symbol</label>
            <input
              value={filter.symbol}
              onChange={(e) => setFilter((f) => ({ ...f, symbol: e.target.value }))}
              placeholder="เช่น AAPL, BTC-USD"
              className="w-full bg-white border border-slate-200 text-slate-900 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500 placeholder-slate-400"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-slate-500 text-sm block mb-1">Timeframe</label>
              <select
                value={filter.timeframe}
                onChange={(e) => setFilter((f) => ({ ...f, timeframe: e.target.value }))}
                className="w-full bg-white border border-slate-200 text-slate-900 rounded-lg px-4 py-2.5 text-sm focus:outline-none"
              >
                <option value="">ทั้งหมด</option>
                <option value="1d">1 วัน</option>
                <option value="1w">1 สัปดาห์</option>
                <option value="1m">1 เดือน</option>
                <option value="3m">3 เดือน</option>
              </select>
            </div>
            <div>
              <label className="text-slate-500 text-sm block mb-1">Status</label>
              <select
                value={filter.status}
                onChange={(e) => setFilter((f) => ({ ...f, status: e.target.value }))}
                className="w-full bg-white border border-slate-200 text-slate-900 rounded-lg px-4 py-2.5 text-sm focus:outline-none"
              >
                <option value="">ทั้งหมด</option>
                <option value="pending">รอเทียบผล</option>
                <option value="compared">เทียบแล้ว</option>
              </select>
            </div>
          </div>
        </div>

        {dlError && (
          <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-600">{dlError}</div>
        )}
        <div className="grid grid-cols-2 gap-4 pt-2">
          <button
            onClick={() => handleDownload("csv")}
            disabled={downloading !== null}
            className="flex items-center justify-center gap-3 bg-white hover:bg-slate-50 disabled:opacity-50 border border-slate-200 text-slate-900 rounded-2xl py-4 transition-colors shadow-sm"
          >
            {downloading === "csv" ? <Loader2 className="w-6 h-6 text-blue-600 animate-spin" /> : <FileText className="w-6 h-6 text-blue-600" />}
            <div className="text-left">
              <div className="font-semibold">CSV</div>
              <div className="text-xs text-slate-500">เปิดใน Excel ได้</div>
            </div>
          </button>
          <button
            onClick={() => handleDownload("excel")}
            disabled={downloading !== null}
            className="flex items-center justify-center gap-3 bg-emerald-50 hover:bg-emerald-100 disabled:opacity-50 border border-emerald-200 text-emerald-700 rounded-2xl py-4 transition-colors"
          >
            {downloading === "excel" ? <Loader2 className="w-6 h-6 text-emerald-600 animate-spin" /> : <FileSpreadsheet className="w-6 h-6 text-emerald-600" />}
            <div className="text-left">
              <div className="font-semibold">Excel (.xlsx)</div>
              <div className="text-xs text-emerald-600">รวม Accuracy Summary</div>
            </div>
          </button>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-5">
        <h3 className="text-slate-700 font-medium mb-3">ข้อมูลที่ได้รับใน Report</h3>
        <ul className="space-y-2 text-sm text-slate-500">
          {[
            "Symbol, Timeframe, Created Date",
            "AI Direction (bullish/bearish/neutral)",
            "Entry Price & Target Price",
            "Confidence Score (%)",
            "AI Reasoning (สรุปเหตุผล)",
            "Actual Price & Actual Direction (ถ้าเทียบแล้ว)",
            "Accuracy Score (%)",
            "Sheet แยก: Accuracy Summary ต่อ Symbol (Excel)",
          ].map((item, i) => (
            <li key={i} className="flex items-center gap-2">
              <span className="text-blue-600 text-xs">✓</span> {item}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

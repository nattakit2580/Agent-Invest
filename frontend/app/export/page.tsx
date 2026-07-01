"use client";
import { useState } from "react";
import { Download, FileSpreadsheet, FileText } from "lucide-react";

const API = "/api";

export default function ExportPage() {
  const [filter, setFilter] = useState({ symbol: "", timeframe: "", status: "" });

  const buildUrl = (format: string) => {
    const params = new URLSearchParams();
    if (filter.symbol) params.append("symbol", filter.symbol.toUpperCase());
    if (filter.timeframe) params.append("timeframe", filter.timeframe);
    if (filter.status) params.append("status", filter.status);
    const qs = params.toString();
    return `${API}/export/${format}${qs ? "?" + qs : ""}`;
  };

  const handleDownload = (format: "csv" | "excel") => {
    window.open(buildUrl(format), "_blank");
  };

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-white flex items-center gap-3">
          <Download className="w-8 h-8 text-sky-400" />
          Export รายงาน
        </h1>
        <p className="text-slate-400 mt-1">ดาวน์โหลดผลการวิเคราะห์และความแม่นยำ</p>
      </div>

      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 space-y-5">
        <h2 className="text-white font-semibold">กรองข้อมูล (ไม่บังคับ)</h2>

        <div className="space-y-3">
          <div>
            <label className="text-slate-400 text-sm block mb-1">Symbol</label>
            <input
              value={filter.symbol}
              onChange={(e) => setFilter((f) => ({ ...f, symbol: e.target.value }))}
              placeholder="เช่น AAPL, BTC-USD"
              className="w-full bg-slate-900 border border-slate-600 text-white rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-sky-500"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-slate-400 text-sm block mb-1">Timeframe</label>
              <select
                value={filter.timeframe}
                onChange={(e) => setFilter((f) => ({ ...f, timeframe: e.target.value }))}
                className="w-full bg-slate-900 border border-slate-600 text-white rounded-lg px-4 py-2.5 text-sm focus:outline-none"
              >
                <option value="">ทั้งหมด</option>
                <option value="1d">1 วัน</option>
                <option value="1w">1 สัปดาห์</option>
                <option value="1m">1 เดือน</option>
                <option value="3m">3 เดือน</option>
              </select>
            </div>
            <div>
              <label className="text-slate-400 text-sm block mb-1">Status</label>
              <select
                value={filter.status}
                onChange={(e) => setFilter((f) => ({ ...f, status: e.target.value }))}
                className="w-full bg-slate-900 border border-slate-600 text-white rounded-lg px-4 py-2.5 text-sm focus:outline-none"
              >
                <option value="">ทั้งหมด</option>
                <option value="pending">รอเทียบผล</option>
                <option value="compared">เทียบแล้ว</option>
              </select>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 pt-2">
          <button
            onClick={() => handleDownload("csv")}
            className="flex items-center justify-center gap-3 bg-slate-700 hover:bg-slate-600 border border-slate-600 text-white rounded-xl py-4 transition-colors"
          >
            <FileText className="w-6 h-6 text-sky-400" />
            <div className="text-left">
              <div className="font-semibold">CSV</div>
              <div className="text-xs text-slate-400">เปิดใน Excel ได้</div>
            </div>
          </button>
          <button
            onClick={() => handleDownload("excel")}
            className="flex items-center justify-center gap-3 bg-emerald-900/30 hover:bg-emerald-900/50 border border-emerald-700 text-white rounded-xl py-4 transition-colors"
          >
            <FileSpreadsheet className="w-6 h-6 text-emerald-400" />
            <div className="text-left">
              <div className="font-semibold">Excel (.xlsx)</div>
              <div className="text-xs text-slate-400">รวม Accuracy Summary</div>
            </div>
          </button>
        </div>
      </div>

      <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
        <h3 className="text-slate-300 font-medium mb-3">ข้อมูลที่ได้รับใน Report</h3>
        <ul className="space-y-2 text-sm text-slate-400">
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
              <span className="text-sky-500 text-xs">✓</span> {item}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

"use client";
import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  Legend,
} from "recharts";
import { Sparkles, Brain, Trophy, AlertTriangle, Scale, Info } from "lucide-react";
import { getLearningInsights, type LearningInsights } from "@/lib/api";

const AGENT_LABELS: Record<string, string> = {
  news: "News",
  fundamental: "Fundamental",
  technical: "Technical",
  sentiment: "Sentiment",
};

function accuracyColor(pct: number) {
  return pct >= 65 ? "#10b981" : pct >= 50 ? "#f59e0b" : "#ef4444";
}

export default function InsightsPage() {
  const [data, setData] = useState<LearningInsights | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getLearningInsights().then(setData).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-slate-400 p-8">กำลังโหลด...</div>;
  if (!data) return <div className="text-red-400 p-8">ไม่สามารถโหลดข้อมูลได้</div>;

  const agentNames = Object.keys(data.base_weights);

  const accData = Object.entries(data.agent_accuracy).map(([name, acc]) => ({
    name: AGENT_LABELS[name] ?? name,
    key: name,
    accuracy: Math.round(acc * 100),
    samples: data.agent_samples[name] ?? 0,
  }));

  const weightData = agentNames.map((name) => ({
    name: AGENT_LABELS[name] ?? name,
    base: Math.round((data.base_weights[name] ?? 0) * 100),
    learned: Math.round((data.learned_weights[name] ?? 0) * 100),
  }));

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-white flex items-center gap-3">
          <Sparkles className="w-8 h-8 text-sky-400" />
          ระบบเรียนรู้
        </h1>
        <p className="text-slate-400 mt-1">
          ระบบเทียบผลคาดการณ์กับผลจริง แล้วปรับน้ำหนักการโหวตของแต่ละ Agent ให้แม่นยำขึ้น
        </p>
      </div>

      {/* status banner */}
      <div
        className={`rounded-xl p-5 flex items-start gap-3 border ${
          data.learning_active
            ? "bg-emerald-900/20 border-emerald-700/50"
            : "bg-slate-800 border-slate-700"
        }`}
      >
        <Info
          className={`w-5 h-5 shrink-0 mt-0.5 ${
            data.learning_active ? "text-emerald-400" : "text-slate-400"
          }`}
        />
        <div className="text-sm">
          {data.learning_active ? (
            <>
              <p className="text-emerald-300 font-medium">ระบบกำลังเรียนรู้จากผลจริงแล้ว</p>
              <p className="text-emerald-200/70 mt-1">
                อ้างอิงจากการคาดการณ์ที่เทียบผลแล้ว {data.compared_samples} รายการ — น้ำหนักด้านล่างถูกปรับตามความแม่นยำจริงของแต่ละ Agent
              </p>
            </>
          ) : (
            <>
              <p className="text-slate-200 font-medium">กำลังสะสมข้อมูลเพื่อเริ่มเรียนรู้</p>
              <p className="text-slate-400 mt-1">
                มีข้อมูลเทียบผลแล้ว {data.compared_samples} รายการ (ต้องมีอย่างน้อย 8 รายการจึงจะเริ่มปรับน้ำหนักอัตโนมัติ) — ระหว่างนี้ใช้น้ำหนักมาตรฐาน
              </p>
            </>
          )}
        </div>
      </div>

      {/* best / worst */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-5">
          <p className="text-xs text-slate-400 uppercase tracking-wider">เทียบผลแล้ว</p>
          <p className="text-3xl font-bold text-white mt-1">{data.compared_samples}</p>
          <p className="text-xs text-slate-500 mt-1">รายการ</p>
        </div>
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 flex items-center gap-4">
          <div className="bg-emerald-900/40 p-3 rounded-lg">
            <Trophy className="w-6 h-6 text-emerald-400" />
          </div>
          <div>
            <p className="text-xs text-slate-400 uppercase tracking-wider">Agent แม่นสุด</p>
            <p className="text-xl font-bold text-emerald-400 mt-1">
              {data.best_agent ? AGENT_LABELS[data.best_agent] ?? data.best_agent : "—"}
            </p>
          </div>
        </div>
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 flex items-center gap-4">
          <div className="bg-red-900/40 p-3 rounded-lg">
            <AlertTriangle className="w-6 h-6 text-red-400" />
          </div>
          <div>
            <p className="text-xs text-slate-400 uppercase tracking-wider">ต้องปรับปรุง</p>
            <p className="text-xl font-bold text-red-400 mt-1">
              {data.worst_agent ? AGENT_LABELS[data.worst_agent] ?? data.worst_agent : "—"}
            </p>
          </div>
        </div>
      </div>

      {/* per-agent accuracy */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-1 flex items-center gap-2">
          <Brain className="w-5 h-5 text-sky-400" />
          ความแม่นยำรายตัวของแต่ละ Agent
        </h2>
        <p className="text-slate-500 text-sm mb-5">คำนวณจากทิศทางที่แต่ละ Agent ทายไว้ เทียบกับผลจริง</p>
        {accData.length === 0 ? (
          <div className="text-slate-500 text-sm py-8 text-center">
            ยังไม่มีข้อมูลเทียบผล — เริ่ม{" "}
            <a href="/analyze" className="text-sky-400 hover:underline">
              วิเคราะห์
            </a>{" "}
            แล้วรอเทียบผลตาม timeframe
          </div>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={accData} margin={{ top: 0, right: 0, left: -10, bottom: 0 }}>
                <XAxis dataKey="name" stroke="#64748b" tick={{ fontSize: 12 }} />
                <YAxis domain={[0, 100]} stroke="#64748b" tick={{ fontSize: 12 }} unit="%" />
                <Tooltip
                  cursor={{ fill: "#1e293b" }}
                  contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
                  labelStyle={{ color: "#f1f5f9" }}
                  formatter={(v: number, _n, p) => [`${v}% (${p.payload.samples} ครั้ง)`, "ความแม่นยำ"]}
                />
                <Bar dataKey="accuracy" radius={[4, 4, 0, 0]}>
                  {accData.map((entry, i) => (
                    <Cell key={i} fill={accuracyColor(entry.accuracy)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </>
        )}
      </div>

      {/* base vs learned weights */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-1 flex items-center gap-2">
          <Scale className="w-5 h-5 text-sky-400" />
          น้ำหนักการโหวต: มาตรฐาน vs เรียนรู้แล้ว
        </h2>
        <p className="text-slate-500 text-sm mb-5">
          ระบบเลื่อนน้ำหนักไปหา Agent ที่ทายแม่นกว่าในอดีต (รวมกัน = 100%)
        </p>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={weightData} margin={{ top: 0, right: 0, left: -10, bottom: 0 }}>
            <XAxis dataKey="name" stroke="#64748b" tick={{ fontSize: 12 }} />
            <YAxis stroke="#64748b" tick={{ fontSize: 12 }} unit="%" />
            <Tooltip
              cursor={{ fill: "#1e293b" }}
              contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
              labelStyle={{ color: "#f1f5f9" }}
              formatter={(v: number) => [`${v}%`]}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="base" name="มาตรฐาน" fill="#475569" radius={[4, 4, 0, 0]} />
            <Bar dataKey="learned" name="เรียนรู้แล้ว" fill="#0ea5e9" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <p className="text-xs text-slate-600 text-center pt-2">
        ทุกการวิเคราะห์ใหม่จะอ้างอิงประวัติผลจริงของสินทรัพย์นั้น และใช้น้ำหนักที่เรียนรู้แล้วในการสรุปผล
      </p>
    </div>
  );
}

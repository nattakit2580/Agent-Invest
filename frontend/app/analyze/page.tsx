"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Brain,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertCircle,
  Loader2,
  Check,
  Newspaper,
  BarChart3,
  LineChart,
  Heart,
  ShieldAlert,
} from "lucide-react";
import {
  analyzeStream,
  wakeBackend,
  type Prediction,
  type AnalyzeStreamEvent,
} from "@/lib/api";

const TIMEFRAMES = [
  { value: "1d", label: "1 วัน" },
  { value: "1w", label: "1 สัปดาห์" },
  { value: "1m", label: "1 เดือน" },
  { value: "3m", label: "3 เดือน" },
];

const QUICK_SYMBOLS = ["AAPL", "TSLA", "NVDA", "BTC-USD", "ETH-USD", "PTT.BK", "AOT.BK"];

const ANALYST_ORDER = ["news", "fundamental", "technical", "sentiment"] as const;

const AGENT_META: Record<string, { label: string; Icon: React.ElementType }> = {
  news: { label: "News Agent", Icon: Newspaper },
  fundamental: { label: "Fundamental Agent", Icon: BarChart3 },
  technical: { label: "Technical Agent", Icon: LineChart },
  sentiment: { label: "Sentiment Agent", Icon: Heart },
  _critic: { label: "Risk Critic", Icon: ShieldAlert },
};

const STAGES = [
  { key: "market", label: "ข้อมูลตลาด" },
  { key: "news", label: "ข่าว" },
  { key: "agents", label: "Agents" },
  { key: "synthesis", label: "สังเคราะห์" },
  { key: "critic", label: "ตรวจทาน" },
  { key: "saving", label: "บันทึก" },
];

type AgentOutput = Record<string, unknown>;
type SynthesisData = Extract<AnalyzeStreamEvent, { type: "synthesis" }>;

function dirColor(d: string) {
  return d === "bullish" ? "text-emerald-400" : d === "bearish" ? "text-red-400" : "text-slate-400";
}
function dirBar(d: string) {
  return d === "bullish" ? "bg-emerald-500" : d === "bearish" ? "bg-red-500" : "bg-slate-500";
}
function dirBorder(d: string) {
  return d === "bullish" ? "border-emerald-700" : d === "bearish" ? "border-red-700" : "border-slate-600";
}
function DirectionIcon({ d, className }: { d: string; className?: string }) {
  if (d === "bullish") return <TrendingUp className={className} />;
  if (d === "bearish") return <TrendingDown className={className} />;
  return <Minus className={className} />;
}

/** Reveals text one character at a time (typewriter). Restarts only when `text` changes. */
function Typewriter({ text, speed = 10, className }: { text: string; speed?: number; className?: string }) {
  const [shown, setShown] = useState("");
  useEffect(() => {
    if (!text) {
      setShown("");
      return;
    }
    let i = 0;
    setShown("");
    const id = setInterval(() => {
      i += 1;
      setShown(text.slice(0, i));
      if (i >= text.length) clearInterval(id);
    }, speed);
    return () => clearInterval(id);
  }, [text, speed]);
  return <span className={className}>{shown}</span>;
}

function AgentCard({ name, output }: { name: string; output: AgentOutput | null }) {
  const meta = AGENT_META[name] ?? { label: name, Icon: Brain };
  const Icon = meta.Icon;

  if (!output) {
    return (
      <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-5 animate-pulse">
        <div className="flex items-center gap-2 text-slate-400">
          <Icon className="w-4 h-4" />
          <span className="text-sm font-medium">{meta.label}</span>
          <Loader2 className="w-3.5 h-3.5 animate-spin ml-auto text-sky-400" />
        </div>
        <div className="mt-4 space-y-2">
          <div className="h-2 bg-slate-700 rounded w-full" />
          <div className="h-2 bg-slate-700 rounded w-4/5" />
          <div className="h-2 bg-slate-700 rounded w-2/3" />
        </div>
      </div>
    );
  }

  const isCritic = name === "_critic";
  const dir = (isCritic ? output.revised_direction : output.direction) as string || "neutral";
  const conf = typeof output.confidence === "number" ? (output.confidence as number) : 0;
  const summary = ((isCritic ? output.critique : output.summary) as string) || "";
  const keyPoints = ((isCritic ? output.counter_points : output.key_points) as string[]) || [];

  return (
    <div className={`bg-slate-800 border rounded-xl p-5 ${dirBorder(dir)} animate-[fadeIn_0.3s_ease-out]`}>
      <div className="flex items-center justify-between mb-3 gap-3">
        <span className="text-white font-semibold text-sm flex items-center gap-2">
          <Icon className="w-4 h-4 text-sky-400" />
          {meta.label}
        </span>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`text-xs font-medium capitalize ${dirColor(dir)}`}>{dir}</span>
          {!isCritic && <span className="text-slate-500 text-xs">{(conf * 100).toFixed(0)}%</span>}
        </div>
      </div>
      {!isCritic && (
        <div className="w-full bg-slate-700 rounded-full h-1 mb-3">
          <div
            className={`h-1 rounded-full transition-all duration-500 ${dirBar(dir)}`}
            style={{ width: `${Math.max(0, Math.min(conf, 1)) * 100}%` }}
          />
        </div>
      )}
      {summary && (
        <p className="text-slate-300 text-xs leading-relaxed mb-2">
          <Typewriter text={summary} />
        </p>
      )}
      <ul className="space-y-1">
        {keyPoints.slice(0, 3).map((pt, i) => (
          <li key={i} className="text-slate-500 text-xs flex items-start gap-1">
            <span className="text-sky-500 mt-0.5">•</span> {pt}
          </li>
        ))}
      </ul>
    </div>
  );
}

function StageStepper({ current, done }: { current: string; done: boolean }) {
  const activeIdx = done ? STAGES.length : STAGES.findIndex((s) => s.key === current);
  return (
    <div className="flex items-center gap-1 flex-wrap">
      {STAGES.map((s, i) => {
        const state = i < activeIdx ? "done" : i === activeIdx ? "active" : "todo";
        return (
          <div key={s.key} className="flex items-center gap-1">
            <span
              className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border transition-colors ${
                state === "done"
                  ? "border-emerald-700 bg-emerald-900/30 text-emerald-300"
                  : state === "active"
                  ? "border-sky-600 bg-sky-900/40 text-sky-200"
                  : "border-slate-700 bg-slate-800 text-slate-500"
              }`}
            >
              {state === "done" ? (
                <Check className="w-3 h-3" />
              ) : state === "active" ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <span className="w-3 h-3 inline-block rounded-full border border-current opacity-50" />
              )}
              {s.label}
            </span>
            {i < STAGES.length - 1 && <span className="w-2 h-px bg-slate-700" />}
          </div>
        );
      })}
    </div>
  );
}

export default function AnalyzePage() {
  const router = useRouter();
  const [symbol, setSymbol] = useState("");
  const [timeframe, setTimeframe] = useState("1w");
  const [phase, setPhase] = useState<"idle" | "running" | "done" | "error">("idle");
  const [stage, setStage] = useState("market");
  const [statusMsg, setStatusMsg] = useState("");
  const [agents, setAgents] = useState<Record<string, AgentOutput>>({});
  const [synthesis, setSynthesis] = useState<SynthesisData | null>(null);
  const [critic, setCritic] = useState<AgentOutput | null>(null);
  const [result, setResult] = useState<Prediction | null>(null);
  const [error, setError] = useState("");
  const abortRef = useRef<AbortController | null>(null);

  // Warm up the (possibly spun-down) backend as soon as the page opens.
  useEffect(() => {
    wakeBackend();
    return () => abortRef.current?.abort();
  }, []);

  const reset = () => {
    setPhase("idle");
    setAgents({});
    setSynthesis(null);
    setCritic(null);
    setResult(null);
    setError("");
    setStatusMsg("");
    setStage("market");
  };

  const handleAnalyze = async () => {
    if (!symbol.trim() || phase === "running") return;
    setPhase("running");
    setAgents({});
    setSynthesis(null);
    setCritic(null);
    setResult(null);
    setError("");
    setStatusMsg("");
    setStage("market");

    const controller = new AbortController();
    abortRef.current = controller;
    let gotFinal = false;

    try {
      await analyzeStream(
        symbol.trim().toUpperCase(),
        timeframe,
        (ev) => {
          switch (ev.type) {
            case "status":
              setStage(ev.stage);
              if (ev.message) setStatusMsg(ev.message);
              break;
            case "agent":
              setAgents((prev) => ({ ...prev, [ev.name]: ev.output }));
              break;
            case "synthesis":
              setSynthesis(ev);
              break;
            case "critic":
              setCritic(ev.output);
              break;
            case "final":
              gotFinal = true;
              setResult(ev.prediction);
              setPhase("done");
              break;
            case "error":
              setError(ev.detail);
              setPhase("error");
              break;
          }
        },
        controller.signal
      );
      if (!gotFinal) {
        setError("การวิเคราะห์ไม่สมบูรณ์ กรุณาลองใหม่อีกครั้ง");
        setPhase("error");
      }
    } catch (e) {
      if (!controller.signal.aborted) {
        setError((e as Error)?.message || "วิเคราะห์ไม่สำเร็จ");
        setPhase("error");
      }
    }
  };

  const running = phase === "running";
  const showResults = running || phase === "done";

  // Header shows the final (critic-adjusted) values once available, else the
  // provisional synthesis values while streaming.
  const headDir = result?.direction ?? synthesis?.direction ?? "neutral";
  const headConf = result?.confidence ?? synthesis?.confidence ?? 0;
  const headPrice = result?.current_price ?? synthesis?.current_price ?? 0;
  const headTarget = result?.target_price ?? synthesis?.target_price ?? null;
  const reasoning = result?.reasoning ?? synthesis?.reasoning ?? "";
  const keyRisks = synthesis?.key_risks ?? [];
  const catalysts = synthesis?.catalysts ?? [];
  const recommendation = synthesis?.recommendation ?? "";

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-white flex items-center gap-3">
          <Brain className="w-8 h-8 text-sky-400" />
          วิเคราะห์การลงทุน
        </h1>
        <p className="text-slate-400 mt-1">ป้อน symbol เพื่อให้ Multi-Agent AI วิเคราะห์</p>
      </div>

      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 space-y-5">
        <div>
          <label className="block text-sm text-slate-400 mb-2">Symbol</label>
          <input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
            placeholder="เช่น AAPL, BTC-USD, PTT.BK"
            className="w-full bg-slate-900 border border-slate-600 text-white rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-sky-500"
          />
          <div className="flex gap-2 mt-2 flex-wrap">
            {QUICK_SYMBOLS.map((s) => (
              <button
                key={s}
                onClick={() => setSymbol(s)}
                className="text-xs px-3 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-full transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm text-slate-400 mb-2">ระยะเวลาการคาดการณ์</label>
          <div className="flex gap-2 flex-wrap">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf.value}
                onClick={() => setTimeframe(tf.value)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  timeframe === tf.value ? "bg-sky-600 text-white" : "bg-slate-700 text-slate-400 hover:bg-slate-600"
                }`}
              >
                {tf.label}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={handleAnalyze}
          disabled={running || !symbol.trim()}
          className="w-full bg-sky-600 hover:bg-sky-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-semibold rounded-lg py-3 flex items-center justify-center gap-2 transition-colors"
        >
          {running ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              {statusMsg || "กำลังวิเคราะห์..."}
            </>
          ) : (
            <>
              <Brain className="w-4 h-4" />
              วิเคราะห์เลย
            </>
          )}
        </button>
        {running && (
          <p className="text-xs text-slate-500 text-center">
            Agents ทยอยแสดงผลระหว่างวิเคราะห์ · ครั้งแรกอาจใช้เวลาถึง ~1 นาทีหากเซิร์ฟเวอร์เพิ่งตื่น
          </p>
        )}
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-xl p-4 flex items-center gap-3 text-red-400">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span className="text-sm">{error}</span>
        </div>
      )}

      {showResults && (
        <div className="space-y-6">
          {/* progress stepper */}
          <StageStepper current={stage} done={phase === "done"} />

          {/* summary header — provisional while streaming, final once done */}
          {(synthesis || result) && (
            <div className={`rounded-xl p-6 border-2 ${
              headDir === "bullish" ? "bg-emerald-900/20 border-emerald-600" :
              headDir === "bearish" ? "bg-red-900/20 border-red-600" : "bg-slate-800 border-slate-600"
            }`}>
              <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className={dirColor(headDir)}>
                      <DirectionIcon d={headDir} className="w-6 h-6" />
                    </span>
                    <h2 className="text-2xl font-bold text-white">{symbol.toUpperCase()}</h2>
                    <span className={`text-lg font-semibold capitalize ${dirColor(headDir)}`}>{headDir}</span>
                    {!result && <span className="text-xs text-slate-500">(ชั่วคราว)</span>}
                  </div>
                  <p className="text-slate-300 mt-3 leading-relaxed text-sm">
                    <Typewriter text={reasoning} />
                  </p>
                </div>
                <div className="text-left md:text-right shrink-0">
                  <div className="text-slate-400 text-xs">Confidence</div>
                  <div className="text-3xl font-bold text-white">{(headConf * 100).toFixed(0)}%</div>
                  <div className="text-slate-400 text-xs mt-2">Entry</div>
                  <div className="text-white font-semibold">${headPrice.toFixed(2)}</div>
                  {headTarget != null && (
                    <>
                      <div className="text-slate-400 text-xs mt-1">Target</div>
                      <div className="text-sky-400 font-semibold">${headTarget.toFixed(2)}</div>
                    </>
                  )}
                </div>
              </div>

              {(keyRisks.length > 0 || catalysts.length > 0 || recommendation) && (
                <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-4 border-t border-slate-700/60 pt-4">
                  {catalysts.length > 0 && (
                    <div>
                      <div className="text-xs font-semibold text-emerald-400 mb-1.5">🚀 ปัจจัยหนุน</div>
                      <ul className="space-y-1">
                        {catalysts.map((c, i) => (
                          <li key={i} className="text-slate-300 text-xs flex gap-1.5">
                            <span className="text-emerald-500">•</span> {c}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {keyRisks.length > 0 && (
                    <div>
                      <div className="text-xs font-semibold text-amber-400 mb-1.5">⚠️ ความเสี่ยง</div>
                      <ul className="space-y-1">
                        {keyRisks.map((r, i) => (
                          <li key={i} className="text-slate-300 text-xs flex gap-1.5">
                            <span className="text-amber-500">•</span> {r}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {recommendation && (
                    <div className="sm:col-span-2">
                      <div className="text-xs font-semibold text-sky-400 mb-1">📌 คำแนะนำ</div>
                      <p className="text-slate-200 text-sm">{recommendation}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* per-agent cards — appear as each finishes */}
          <div>
            <h3 className="text-lg font-semibold text-white mb-3">ผลวิเคราะห์แยก Agent</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {ANALYST_ORDER.map((name) => (
                <AgentCard key={name} name={name} output={agents[name] ?? null} />
              ))}
            </div>
          </div>

          {/* critic */}
          {critic && (
            <div>
              <h3 className="text-lg font-semibold text-white mb-3">การตรวจทานความเสี่ยง</h3>
              <AgentCard name="_critic" output={critic} />
            </div>
          )}

          {phase === "done" && (
            <div className="flex flex-col sm:flex-row gap-3">
              <button
                onClick={() => router.push("/predictions")}
                className="flex-1 bg-slate-700 hover:bg-slate-600 text-white py-3 rounded-lg text-sm font-medium transition-colors"
              >
                ดูประวัติทั้งหมด
              </button>
              <button
                onClick={() => { reset(); setSymbol(""); }}
                className="flex-1 bg-sky-600 hover:bg-sky-500 text-white py-3 rounded-lg text-sm font-medium transition-colors"
              >
                วิเคราะห์ใหม่
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

"use client";
import { useEffect, useState } from "react";
import { FlaskConical, TrendingUp, TrendingDown, Minus, AlertCircle, Loader2, BookOpen, Database, Network, Sprout } from "lucide-react";
import {
  deepResearch,
  getKnowledgeStats,
  seedKnowledgeGraph,
  type DeepResearchRequest,
  type DeepResearchResult,
  type KnowledgeStats,
} from "@/lib/api";

const TIMEFRAMES = [
  { value: "1d", label: "1 วัน" },
  { value: "1w", label: "1 สัปดาห์" },
  { value: "1m", label: "1 เดือน" },
  { value: "3m", label: "3 เดือน" },
];

const REGIME_STYLES: Record<string, string> = {
  volatile: "bg-amber-50 text-amber-700 border border-amber-200",
  trending_up: "bg-emerald-50 text-emerald-700 border border-emerald-200",
  trending_down: "bg-red-50 text-red-700 border border-red-200",
  earnings_season: "bg-violet-50 text-violet-700 border border-violet-200",
  news_driven: "bg-blue-50 text-blue-700 border border-blue-200",
  sideways: "bg-slate-50 text-slate-600 border border-slate-200",
};

function RegimeBadge({ regime }: { regime: string }) {
  const style = REGIME_STYLES[regime] ?? "bg-slate-50 text-slate-600 border border-slate-200";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${style}`}>
      {regime.replace(/_/g, " ")}
    </span>
  );
}

function AgentCard({ name, output }: { name: string; output: Record<string, unknown> }) {
  const dir = output.direction as string;
  const conf = (output.confidence as number) || 0;
  const summary = output.summary as string;
  const keyPoints = (output.key_points as string[]) || [];

  const borderColor =
    dir === "bullish" ? "border-l-emerald-500" :
    dir === "bearish" ? "border-l-red-500" :
    "border-l-slate-300";
  const labelColor =
    dir === "bullish" ? "text-emerald-600" :
    dir === "bearish" ? "text-red-600" :
    "text-slate-500";

  const agentNames: Record<string, string> = {
    news: "News Agent",
    fundamental: "Fundamental Agent",
    technical: "Technical Agent",
    sentiment: "Sentiment Agent",
    deep_research: "Deep Research Agent",
  };

  return (
    <div className={`bg-white border border-slate-200 border-l-4 rounded-2xl shadow-sm p-5 ${borderColor}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-slate-900 font-semibold text-sm">{agentNames[name] ?? name}</span>
        <div className="flex items-center gap-2">
          <span className={`text-xs font-medium ${labelColor}`}>{dir}</span>
          <span className="text-slate-400 text-xs">{(conf * 100).toFixed(0)}%</span>
        </div>
      </div>
      <div className="w-full bg-slate-100 rounded-full h-1 mb-3">
        <div
          className={`h-1 rounded-full ${dir === "bullish" ? "bg-emerald-500" : dir === "bearish" ? "bg-red-500" : "bg-slate-400"}`}
          style={{ width: `${conf * 100}%` }}
        />
      </div>
      <p className="text-slate-600 text-xs leading-relaxed mb-2">{summary}</p>
      <ul className="space-y-1">
        {keyPoints.slice(0, 3).map((pt, i) => (
          <li key={i} className="text-slate-500 text-xs flex items-start gap-1">
            <span className="text-blue-600 mt-0.5">•</span> {pt}
          </li>
        ))}
      </ul>
    </div>
  );
}

function StatChip({ label, value, color = "bg-slate-100 text-slate-700 border-slate-200" }: {
  label: string; value: number | string; color?: string
}) {
  return (
    <div className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium ${color}`}>
      <span className="text-xs text-opacity-70">{label}</span>
      <span className="font-bold">{value}</span>
    </div>
  );
}

export default function DeepResearchPage() {
  const [symbol, setSymbol] = useState("");
  const [timeframe, setTimeframe] = useState("1w");
  const [maxPapers, setMaxPapers] = useState(5);
  const [maxFilings, setMaxFilings] = useState(3);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<DeepResearchResult | null>(null);
  const [knowledgeStats, setKnowledgeStats] = useState<KnowledgeStats | null>(null);
  const [knowledgeLoading, setKnowledgeLoading] = useState(true);
  const [seedLoading, setSeedLoading] = useState(false);
  const [seedMessage, setSeedMessage] = useState("");

  useEffect(() => {
    getKnowledgeStats()
      .then(setKnowledgeStats)
      .catch(() => setKnowledgeStats(null))
      .finally(() => setKnowledgeLoading(false));
  }, []);

  const handleResearch = async () => {
    if (!symbol.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const req: DeepResearchRequest = {
        symbol: symbol.trim().toUpperCase(),
        timeframe,
        max_papers: maxPapers,
        max_filings: maxFilings,
      };
      const data = await deepResearch(req);
      setResult(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "วิเคราะห์ไม่สำเร็จ";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleSeedGraph = async () => {
    setSeedLoading(true);
    setSeedMessage("");
    try {
      const res = await seedKnowledgeGraph();
      setSeedMessage(res?.message ?? "Seed graph สำเร็จ");
      const stats = await getKnowledgeStats();
      setKnowledgeStats(stats);
    } catch {
      setSeedMessage("ไม่สามารถ seed knowledge graph ได้");
    } finally {
      setSeedLoading(false);
    }
  };

  const directionIcon = (d: string) =>
    d === "bullish" ? <TrendingUp className="w-6 h-6" /> :
    d === "bearish" ? <TrendingDown className="w-6 h-6" /> :
    <Minus className="w-6 h-6" />;

  const totalEntities = knowledgeStats
    ? Object.values(knowledgeStats.knowledge_graph.entities).reduce((a, b) => a + b, 0)
    : 0;
  const totalDocs = knowledgeStats
    ? Object.values(knowledgeStats.knowledge_docs).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-3">
          <FlaskConical className="w-8 h-8 text-blue-600" />
          Deep Research
        </h1>
        <p className="text-slate-500 mt-1">วิเคราะห์เชิงลึกจากงานวิจัย, SEC filings และ Knowledge Graph</p>
      </div>

      {/* Form */}
      <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6 space-y-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-slate-500 mb-2">Symbol</label>
            <input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleResearch()}
              placeholder="เช่น AAPL, BTC-USD, PTT.BK"
              className="w-full bg-white border border-slate-200 text-slate-900 rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-blue-500 placeholder-slate-400"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-500 mb-2">Timeframe</label>
            <div className="flex gap-2">
              {TIMEFRAMES.map((tf) => (
                <button
                  key={tf.value}
                  onClick={() => setTimeframe(tf.value)}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    timeframe === tf.value
                      ? "bg-blue-600 text-white"
                      : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {tf.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-slate-500 mb-2">
              Max Papers <span className="text-slate-400">(1–10)</span>
            </label>
            <input
              type="number"
              min={1}
              max={10}
              value={maxPapers}
              onChange={(e) => setMaxPapers(Number(e.target.value))}
              className="w-full bg-white border border-slate-200 text-slate-900 rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-500 mb-2">
              Max Filings <span className="text-slate-400">(0–10)</span>
            </label>
            <input
              type="number"
              min={0}
              max={10}
              value={maxFilings}
              onChange={(e) => setMaxFilings(Number(e.target.value))}
              className="w-full bg-white border border-slate-200 text-slate-900 rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        <button
          onClick={handleResearch}
          disabled={loading || !symbol.trim()}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-slate-100 disabled:text-slate-400 text-white font-semibold rounded-lg py-3 flex items-center justify-center gap-2 transition-colors"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              กำลังค้นคว้าเอกสาร...
            </>
          ) : (
            <>
              <FlaskConical className="w-4 h-4" />
              วิเคราะห์เชิงลึก
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-2xl p-4 flex items-center gap-3 text-red-600">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span className="text-sm">{error}</span>
        </div>
      )}

      {result && (
        <div className="space-y-6">
          {/* Stats row */}
          <div className="flex flex-wrap gap-3">
            <StatChip
              label="Papers Found"
              value={result.deep_research.papers_found}
              color="bg-blue-50 text-blue-700 border-blue-200"
            />
            <StatChip
              label="Filings Found"
              value={result.deep_research.filings_found}
              color="bg-violet-50 text-violet-700 border-violet-200"
            />
            <StatChip
              label="New Docs Indexed"
              value={result.deep_research.new_docs_indexed}
              color="bg-emerald-50 text-emerald-700 border-emerald-200"
            />
            {result.elapsed_seconds > 0 && (
              <StatChip
                label="Time"
                value={`${result.elapsed_seconds.toFixed(1)}s`}
                color="bg-slate-50 text-slate-600 border-slate-200"
              />
            )}
          </div>

          {/* Direction result card */}
          <div className={`rounded-2xl p-6 border-2 ${
            result.direction === "bullish" ? "bg-emerald-50 border-emerald-200" :
            result.direction === "bearish" ? "bg-red-50 border-red-200" :
            "bg-white border-slate-200"
          }`}>
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-3 flex-wrap">
                  <span className={`${result.direction === "bullish" ? "text-emerald-600" : result.direction === "bearish" ? "text-red-600" : "text-slate-500"}`}>
                    {directionIcon(result.direction)}
                  </span>
                  <h2 className="text-2xl font-bold text-slate-900">{result.symbol}</h2>
                  <span className={`text-lg font-semibold capitalize ${
                    result.direction === "bullish" ? "text-emerald-600" :
                    result.direction === "bearish" ? "text-red-600" : "text-slate-500"
                  }`}>{result.direction}</span>
                  {result.market_regime && <RegimeBadge regime={result.market_regime} />}
                </div>
                <p className="text-slate-600 mt-3 leading-relaxed text-sm">{result.reasoning}</p>
              </div>
              <div className="text-right ml-6 flex-shrink-0">
                <div className="text-slate-500 text-xs">Confidence</div>
                <div className="text-3xl font-bold text-slate-900">{(result.confidence * 100).toFixed(0)}%</div>
                <div className="text-slate-500 text-xs mt-2">Entry</div>
                <div className="text-slate-900 font-semibold">${result.current_price.toFixed(2)}</div>
                {result.target_price && (
                  <>
                    <div className="text-slate-500 text-xs mt-1">Target</div>
                    <div className="text-blue-600 font-semibold">${result.target_price.toFixed(2)}</div>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Research Highlights */}
          {result.deep_research.highlights && result.deep_research.highlights.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6">
              <h3 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
                <BookOpen className="w-5 h-5 text-blue-600" />
                Research Highlights
              </h3>
              <ul className="space-y-3">
                {result.deep_research.highlights.map((h, i) => (
                  <li key={i} className="flex items-start gap-3 text-sm text-slate-600">
                    <span className="text-blue-600 font-bold mt-0.5">{i + 1}.</span>
                    <span className="leading-relaxed">{h}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Agent outputs */}
          {result.agent_outputs && Object.keys(result.agent_outputs).length > 0 && (
            <div>
              <h3 className="text-lg font-semibold text-slate-900 mb-3">ผลวิเคราะห์แยก Agent</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Object.entries(result.agent_outputs).map(([name, output]) => (
                  <AgentCard key={name} name={name} output={output as Record<string, unknown>} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Knowledge Base Stats */}
      <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
            <Database className="w-5 h-5 text-blue-600" />
            Knowledge Base
          </h2>
          <button
            onClick={handleSeedGraph}
            disabled={seedLoading}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 text-emerald-700 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          >
            {seedLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sprout className="w-4 h-4" />
            )}
            Seed Knowledge Graph
          </button>
        </div>

        {seedMessage && (
          <div className="mb-4 text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-2">
            {seedMessage}
          </div>
        )}

        {knowledgeLoading ? (
          <div className="text-slate-500 text-sm">กำลังโหลด knowledge stats...</div>
        ) : knowledgeStats === null ? (
          <div className="text-slate-400 text-sm">ไม่สามารถโหลด knowledge stats ได้</div>
        ) : (
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-slate-50 rounded-xl p-4 text-center border border-slate-200">
              <div className="flex justify-center mb-2">
                <Database className="w-6 h-6 text-blue-600" />
              </div>
              <div className="text-2xl font-bold text-slate-900">{totalDocs}</div>
              <div className="text-xs text-slate-500 mt-1">Documents</div>
              <div className="mt-2 space-y-1">
                {Object.entries(knowledgeStats.knowledge_docs).map(([type, count]) => (
                  <div key={type} className="flex justify-between text-xs text-slate-500">
                    <span>{type}</span>
                    <span className="font-medium text-slate-700">{count}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-slate-50 rounded-xl p-4 text-center border border-slate-200">
              <div className="flex justify-center mb-2">
                <Network className="w-6 h-6 text-violet-600" />
              </div>
              <div className="text-2xl font-bold text-slate-900">{totalEntities}</div>
              <div className="text-xs text-slate-500 mt-1">Entities</div>
              <div className="mt-2 space-y-1">
                {Object.entries(knowledgeStats.knowledge_graph.entities).map(([type, count]) => (
                  <div key={type} className="flex justify-between text-xs text-slate-500">
                    <span>{type}</span>
                    <span className="font-medium text-slate-700">{count}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-slate-50 rounded-xl p-4 text-center border border-slate-200">
              <div className="flex justify-center mb-2">
                <Network className="w-6 h-6 text-emerald-600" />
              </div>
              <div className="text-2xl font-bold text-slate-900">{knowledgeStats.knowledge_graph.relationships}</div>
              <div className="text-xs text-slate-500 mt-1">Relationships</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

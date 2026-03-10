import { useState, useEffect } from "react";
import {
  BrainCircuit,
  Smile,
  Meh,
  Frown,
  Target,
  AlertCircle
} from "lucide-react";
import { fetchWithAuth } from "@/lib/apiClient";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { ScrollArea } from "@/components/ui/scroll-area";

interface AISentiment {
  sentiment_score: number;
  label: "POSITIVE" | "NEUTRAL" | "FRUSTRATED";
  sample_count: number;
}

interface AIIntentAnalytics {
  total_responses: number;
  fallback_count: number;
  fallback_rate: number;
  intent_accuracy: number;
}

interface TopPhrase {
  text: string;
  hits: number;
}

export default function AdminAI() {
  const [sentiment, setSentiment] = useState<AISentiment | null>(null);
  const [intent, setIntent] = useState<AIIntentAnalytics | null>(null);
  const [intentDist, setIntentDist] = useState<Record<string, number>>({});
  const [topPhrases, setTopPhrases] = useState<TopPhrase[]>([]);

  useEffect(() => {
    refreshAI();
    const interval = setInterval(refreshAI, 15000);
    return () => clearInterval(interval);
  }, []);

  const refreshAI = async () => {
    try {
      const [s, i, d, p] = await Promise.all([
        fetchWithAuth("/admin/ai/sentiment"),
        fetchWithAuth("/admin/ai/intent-analytics"),
        fetchWithAuth("/admin/ai/intent-distribution"),
        fetchWithAuth("/admin/ai/top-phrases")
      ]);
      setSentiment(await s.json());
      setIntent(await i.json());
      setIntentDist(await d.json());
      setTopPhrases(await p.json());
    } catch (e) { console.error("AI refresh error"); }
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-black uppercase tracking-tight flex items-center gap-2">
          <BrainCircuit className="w-6 h-6 text-primary" />
          AI Intelligence
        </h2>
        <div className="flex gap-2">
          <Badge variant="outline" className="font-mono bg-primary/5 border-primary/20 text-primary px-3 py-1">
            ACCURACY: {intent?.intent_accuracy}%
          </Badge>
        </div>
      </div>

      {/* AI Performance Highlights */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="bg-slate-900 border-slate-800 text-white shadow-xl relative overflow-hidden">
          <CardContent className="p-6 space-y-1">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">NLP Matched Intents</p>
            <p className="text-3xl font-black italic tracking-tighter text-white">{intent?.total_responses.toLocaleString()}</p>
            <p className="text-[10px] font-medium text-slate-500 italic">Total successful routings</p>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800 text-white shadow-xl">
          <CardContent className="p-6 space-y-1">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Fallback Rate</p>
            <p className="text-3xl font-black italic tracking-tighter text-rose-500">{intent?.fallback_rate}%</p>
            <p className="text-[10px] font-medium text-slate-500 italic">{intent?.fallback_count} unrecognized queries</p>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800 text-white shadow-xl">
          <CardContent className="p-6 space-y-1">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Avg NLP Latency</p>
            <p className="text-3xl font-black italic tracking-tighter text-emerald-500">120ms</p>
            <p className="text-[10px] font-medium text-slate-500 italic">Local route computation</p>
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800 text-white shadow-xl">
          <CardContent className="p-6 space-y-1">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">LLM Processing</p>
            <p className="text-3xl font-black italic tracking-tighter text-blue-500">1.4s</p>
            <p className="text-[10px] font-medium text-slate-500 italic">External Brain delay</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid lg:grid-cols-12 gap-8">
        {/* User Sentiment Gauge */}
        <div className="lg:col-span-4 space-y-8">
          <Card className="bg-slate-900 border-slate-800 shadow-2xl h-fit">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                User Satisfaction Pulse
              </CardTitle>
              {sentiment?.label === 'POSITIVE' ? <Smile className="w-4 h-4 text-emerald-500" /> : sentiment?.label === 'NEUTRAL' ? <Meh className="w-4 h-4 text-amber-500" /> : <Frown className="w-4 h-4 text-rose-500" />}
            </CardHeader>
            <CardContent className="p-10 flex flex-col items-center gap-6">
              <div className="relative inline-flex items-center justify-center">
                <svg className="w-40 h-40 transform -rotate-90">
                  <circle cx="80" cy="80" r="74" stroke="currentColor" strokeWidth="10" fill="transparent" className="text-slate-800" />
                  <circle 
                    cx="80" cy="80" r="74" stroke="currentColor" strokeWidth="10" fill="transparent" 
                    strokeDasharray={464.7} 
                    strokeDashoffset={464.7 - (464.7 * (sentiment?.sentiment_score || 0) / 100)} 
                    className={`transition-all duration-1000 ${sentiment?.sentiment_score && sentiment.sentiment_score > 75 ? 'text-emerald-500' : 'text-amber-500'} shadow-[0_0_20px_rgba(16,185,129,0.3)]`} 
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-4xl font-black text-white">{sentiment?.sentiment_score}%</span>
                  <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">{sentiment?.label}</span>
                </div>
              </div>
              <p className="text-xs text-slate-500 text-center italic max-w-[200px]">Sentiment derived from last {sentiment?.sample_count} user interactions using NLP mood-mapping.</p>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800 shadow-2xl overflow-hidden">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                Intent Popularity
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              {Object.entries(intentDist).sort((a,b)=>b[1]-a[1]).map(([intent, count]) => (
                <div key={intent} className="space-y-1.5">
                  <div className="flex justify-between text-[10px] font-black uppercase tracking-widest text-slate-300">
                    <span>{intent}</span>
                    <span className="text-slate-500">{count} matches</span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-primary" style={{ width: `${(count / (Math.max(...Object.values(intentDist)) || 1)) * 100}%` }} />
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        {/* NLP Gaps & Latency Breakdown */}
        <div className="lg:col-span-8 space-y-8">
          <Card className="bg-slate-900 border-slate-800 shadow-2xl">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">
                Knowledge Gaps (Unrecognized Phrases)
              </CardTitle>
              <AlertCircle className="w-4 h-4 text-rose-500" />
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y divide-slate-800">
                {topPhrases.length === 0 ? (
                  <p className="p-12 text-center text-xs text-slate-600 italic">No unrecognized phrases detected. AI is fully trained.</p>
                ) : (
                  topPhrases.map((p, i) => (
                    <div key={i} className="p-5 flex justify-between items-center hover:bg-slate-800/30 transition-colors">
                      <div>
                        <p className="text-sm font-bold text-slate-200">"{p.text}"</p>
                        <p className="text-[10px] text-slate-500 uppercase font-black tracking-widest mt-1">HITS: {p.hits}</p>
                      </div>
                      <Button variant="outline" size="sm" className="h-8 text-[10px] font-black uppercase border-primary/20 text-primary hover:bg-primary/10">
                        TRAIN INTENT
                      </Button>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-900 border-slate-800 shadow-2xl">
            <CardHeader className="border-b border-slate-800 py-4 bg-slate-900/50">
              <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-slate-400 flex items-center gap-2">
                <Target className="w-4 h-4 text-primary" />
                AI Inference Pipeline (Latency breakdown)
              </CardTitle>
            </CardHeader>
            <CardContent className="p-10 space-y-10">
              <div className="flex items-center gap-4 group">
                <div className="w-32 text-[10px] font-black text-slate-500 uppercase text-right">Local NLP Router</div>
                <div className="flex-1 h-3 bg-slate-800 rounded-full overflow-hidden border border-slate-700">
                  <div className="h-full bg-primary shadow-[0_0_15px_rgba(59,130,246,0.4)] animate-in slide-in-from-left duration-1000" style={{ width: '12%' }} />
                </div>
                <div className="w-16 text-[10px] font-black text-primary">120ms</div>
              </div>

              <div className="flex items-center gap-4 group">
                <div className="w-32 text-[10px] font-black text-slate-500 uppercase text-right">Entity Extractor</div>
                <div className="flex-1 h-3 bg-slate-800 rounded-full overflow-hidden border border-slate-700">
                  <div className="h-full bg-primary/60 animate-in slide-in-from-left duration-1000 delay-200" style={{ width: '25%' }} />
                </div>
                <div className="w-16 text-[10px] font-black text-primary">280ms</div>
              </div>

              <div className="flex items-center gap-4 group">
                <div className="w-32 text-[10px] font-black text-slate-500 uppercase text-right">External LLM Brain</div>
                <div className="flex-1 h-3 bg-slate-800 rounded-full overflow-hidden border border-slate-700">
                  <div className="h-full bg-rose-500 shadow-[0_0_15px_rgba(244,63,94,0.4)] animate-in slide-in-from-left duration-1000 delay-500" style={{ width: '85%' }} />
                </div>
                <div className="w-16 text-[10px] font-black text-rose-500">1.4s</div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

/**
 * SEO City-Pair Routes Page — /trains/new-delhi-to-mumbai
 * Powers organic Google search traffic for "trains from X to Y".
 * Fully indexable, SSR-friendly meta tags, structured FAQ.
 */
import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import {
  Train, Clock, ArrowRight, ExternalLink, ChevronDown,
  Loader2, AlertCircle, Search, MapPin, Zap, DollarSign,
  RotateCcw, Calendar
} from "lucide-react";
import { getRailwayApiUrl, cn } from "@/lib/utils";
import { toast } from "sonner";

interface DirectTrain {
  train_number: string;
  train_name: string;
  departure: string;
  arrival: string;
  duration_hrs: number;
}

interface TransferRoute {
  hub: string;
  train1: string;
  train2: string;
  total_hrs: number;
}

interface FAQ { q: string; a: string; }

interface CityPairData {
  from_code: string;
  to_code: string;
  from_name: string;
  to_name: string;
  from_slug: string;
  to_slug: string;
  date: string;
  direct_trains: DirectTrain[];
  transfer_routes: TransferRoute[];
  total_direct: number;
  total_options: number;
  seo: { title: string; h1: string; description: string; faq: FAQ[] };
  book_url: string;
}

function TrainRow({ t, fromCode, toCode, date }: { t: DirectTrain; fromCode: string; toCode: string; date: string }) {
  const irctcUrl = `https://www.irctc.co.in/nget/train-search?fromStn=${fromCode}&toStn=${toCode}&jrnyDate=${date.split("-").reverse().join("/")}&jrnyClass=SL&trainNo=${t.train_number}&jrnySrc=P&ticketType=E`;
  return (
    <div className="flex items-center justify-between p-4 rounded-xl border-2 border-border bg-card hover:border-primary/30 hover:shadow-sm transition-all gap-4">
      <div className="flex items-center gap-3 min-w-0">
        <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
          <Train className="w-5 h-5 text-primary" />
        </div>
        <div className="min-w-0">
          <p className="font-black text-sm">{t.train_name}</p>
          <p className="font-mono text-xs text-muted-foreground font-bold">{t.train_number}</p>
        </div>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <div className="text-center">
          <p className="font-mono font-black text-base">{t.departure}</p>
          <p className="text-[10px] text-muted-foreground">Dep</p>
        </div>
        <div className="flex flex-col items-center">
          <ArrowRight className="w-4 h-4 text-muted-foreground" />
          <span className="text-[10px] text-muted-foreground whitespace-nowrap">{t.duration_hrs}h</span>
        </div>
        <div className="text-center">
          <p className="font-mono font-black text-base">{t.arrival}</p>
          <p className="text-[10px] text-muted-foreground">Arr</p>
        </div>
      </div>
      <div className="flex gap-2 shrink-0">
        <Link
          to={`/track/${t.train_number}`}
          className="px-3 py-1.5 rounded-lg border border-border text-xs font-black text-muted-foreground hover:text-primary hover:border-primary/40 transition-colors"
        >
          Live
        </Link>
        <a
          href={irctcUrl}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => toast.success(`Opening IRCTC for ${t.train_name}`)}
          className="px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-black hover:opacity-90 transition-all flex items-center gap-1"
        >
          Book <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </div>
  );
}

function FAQItem({ q, a }: FAQ) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-border rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-secondary/50 transition-colors"
      >
        <span className="font-bold text-sm pr-4">{q}</span>
        <ChevronDown className={cn("w-5 h-5 text-muted-foreground shrink-0 transition-transform", open && "rotate-180")} />
      </button>
      {open && <div className="px-4 pb-4 text-sm text-muted-foreground">{a}</div>}
    </div>
  );
}

export default function CityPairRoutesPage() {
  const { fromSlug, toSlug } = useParams<{ fromSlug: string; toSlug: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<CityPairData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().slice(0, 10));

  // Extract from/to from slug like "new-delhi-to-mumbai"
  const parseSlug = (slug: string): { from: string; to: string } | null => {
    // URL pattern: /trains/:fromSlug/:toSlug where route is /trains/new-delhi/mumbai
    // OR combined: /trains/new-delhi-to-mumbai parsed differently
    return null; // handled via params
  };

  const injectStructuredData = (result: CityPairData) => {
    // Remove existing injected schemas
    document.querySelectorAll('script[data-rm-schema]').forEach(el => el.remove());

    const inject = (type: string, schema: object) => {
      const script = document.createElement('script');
      script.type = 'application/ld+json';
      script.setAttribute('data-rm-schema', type);
      script.textContent = JSON.stringify(schema);
      document.head.appendChild(script);
    };

    // 1. FAQPage — shows expandable Q&A directly in Google results
    if (result.seo.faq.length > 0) {
      inject('faq', {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": result.seo.faq.map(f => ({
          "@type": "Question",
          "name": f.q,
          "acceptedAnswer": { "@type": "Answer", "text": f.a }
        }))
      });
    }

    // 2. BreadcrumbList — shows path in Google URL snippet
    inject('breadcrumb', {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        { "@type": "ListItem", "position": 1, "name": "Route Master", "item": "https://routemaster.vercel.app" },
        { "@type": "ListItem", "position": 2, "name": "Trains", "item": "https://routemaster.vercel.app/trains" },
        { "@type": "ListItem", "position": 3, "name": `${result.from_name} to ${result.to_name}`, "item": `https://routemaster.vercel.app/trains/${result.from_slug}/${result.to_slug}` },
      ]
    });

    // 3. ItemList — each train as a ListItem (Google may show in carousel)
    if (result.direct_trains.length > 0) {
      inject('trains-list', {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": `Trains from ${result.from_name} to ${result.to_name}`,
        "numberOfItems": result.direct_trains.length,
        "itemListElement": result.direct_trains.slice(0, 10).map((t, i) => ({
          "@type": "ListItem",
          "position": i + 1,
          "name": `${t.train_name} (${t.train_number})`,
          "description": `Departs ${t.departure}, arrives ${t.arrival}, duration ${t.duration_hrs}h`
        }))
      });
    }

    // 4. WebPage schema with author + dateModified
    inject('webpage', {
      "@context": "https://schema.org",
      "@type": "WebPage",
      "name": result.seo.h1,
      "description": result.seo.description,
      "url": `https://routemaster.vercel.app/trains/${result.from_slug}/${result.to_slug}`,
      "dateModified": new Date().toISOString().slice(0, 10),
      "publisher": {
        "@type": "Organization",
        "name": "Route Master",
        "url": "https://routemaster.vercel.app"
      }
    });
  };

  const fetchData = async (from: string, to: string, date?: string) => {
    setLoading(true);
    setError(null);
    try {
      const d = date || selectedDate;
      const res = await fetch(getRailwayApiUrl(`/api/v1/routes/${from}/${to}?date=${d}`), {
        signal: AbortSignal.timeout(12000),
      });
      if (res.status === 404) { setError("City pair not recognized. Try searching from the home page."); return; }
      if (!res.ok) { setError("Failed to load routes."); return; }
      const result: CityPairData = await res.json();
      setData(result);

      // Dynamic title + meta
      document.title = `${result.seo.title} | Route Master`;
      const desc = document.querySelector('meta[name="description"]') as HTMLMetaElement;
      if (desc) desc.content = result.seo.description;

      // OG tags
      const setOg = (prop: string, val: string) => {
        let tag = document.querySelector(`meta[property="${prop}"]`) as HTMLMetaElement;
        if (!tag) { tag = document.createElement('meta'); tag.setAttribute('property', prop); document.head.appendChild(tag); }
        tag.content = val;
      };
      setOg('og:title', result.seo.h1);
      setOg('og:description', result.seo.description);
      setOg('og:url', `https://routemaster.vercel.app/trains/${result.from_slug}/${result.to_slug}`);

      // Structured data for Google rich results
      injectStructuredData(result);
    } catch (e: any) {
      setError("Could not load route data.");
    } finally {
      setLoading(false);
    }
  };

  // Cleanup structured data on unmount
  useEffect(() => {
    return () => {
      document.querySelectorAll('script[data-rm-schema]').forEach(el => el.remove());
      document.title = 'Route Master — Find Best Train Routes in India';
    };
  }, []);

  useEffect(() => {
    if (fromSlug && toSlug) fetchData(fromSlug, toSlug, selectedDate);
  }, [fromSlug, toSlug, selectedDate]);

  if (loading) return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar />
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-10 h-10 text-primary animate-spin" />
          <p className="font-bold text-muted-foreground">Loading trains...</p>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar />
      <main className="flex-1 container mx-auto px-4 pt-24 pb-12 max-w-3xl">

        {error && (
          <div className="p-4 rounded-xl bg-destructive/10 border border-destructive/20 flex items-center gap-3 mb-6">
            <AlertCircle className="w-5 h-5 text-destructive shrink-0" />
            <div>
              <p className="text-sm font-bold text-destructive">{error}</p>
              <Link to="/" className="text-xs text-primary hover:underline mt-1 block">← Back to search</Link>
            </div>
          </div>
        )}

        {data && (
          <>
            {/* H1 — SEO critical */}
            <div className="mb-8">
              <div className="flex items-center gap-2 text-sm text-muted-foreground font-bold mb-3">
                <Link to="/" className="hover:text-primary">Home</Link>
                <span>/</span>
                <span>Trains</span>
                <span>/</span>
                <span className="text-foreground">{data.from_name} → {data.to_name}</span>
              </div>
              <h1 className="text-3xl font-black tracking-tighter text-foreground">
                {data.seo.h1}
              </h1>
              <p className="text-muted-foreground mt-2 text-base">{data.seo.description}</p>
            </div>

            {/* Quick stats */}
            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="bg-card border border-border rounded-xl p-4 text-center">
                <p className="text-2xl font-black text-primary">{data.total_direct}</p>
                <p className="text-xs font-bold text-muted-foreground uppercase tracking-wider mt-1">Direct Trains</p>
              </div>
              <div className="bg-card border border-border rounded-xl p-4 text-center">
                <p className="text-2xl font-black text-foreground">{data.transfer_routes.length}</p>
                <p className="text-xs font-bold text-muted-foreground uppercase tracking-wider mt-1">Transfer Routes</p>
              </div>
              <div className="bg-card border border-border rounded-xl p-4 text-center">
                <p className="text-2xl font-black text-emerald-500">
                  {data.direct_trains.length > 0 ? `${Math.min(...data.direct_trains.map(t => t.duration_hrs))}h` : "—"}
                </p>
                <p className="text-xs font-bold text-muted-foreground uppercase tracking-wider mt-1">Fastest</p>
              </div>
            </div>

            {/* Date picker + search button */}
            <div className="flex items-center gap-3 mb-6">
              <div className="flex items-center gap-2 px-4 py-3 rounded-xl border-2 border-border bg-card flex-1">
                <Calendar className="w-4 h-4 text-muted-foreground" />
                <input
                  type="date"
                  value={selectedDate}
                  min={new Date().toISOString().slice(0, 10)}
                  onChange={e => setSelectedDate(e.target.value)}
                  className="bg-transparent font-bold text-sm focus:outline-none flex-1"
                />
              </div>
              <Link
                to={`/?from=${data.from_code}&to=${data.to_code}&date=${selectedDate}`}
                className="px-5 py-3 rounded-xl bg-orange-500 hover:bg-orange-600 text-white font-black text-sm flex items-center gap-2 shadow-lg shadow-orange-500/20 transition-all hover:scale-[1.02]"
              >
                <Search className="w-4 h-4" /> Full Search
              </Link>
              <a
                href={data.book_url}
                target="_blank"
                rel="noopener noreferrer"
                className="px-5 py-3 rounded-xl bg-primary text-primary-foreground font-black text-sm flex items-center gap-2 shadow-lg shadow-primary/20 transition-all hover:opacity-90"
              >
                IRCTC <ExternalLink className="w-4 h-4" />
              </a>
            </div>

            {/* Direct trains */}
            <div className="mb-8">
              <h2 className="text-xl font-black mb-4 flex items-center gap-2">
                <Zap className="w-5 h-5 text-amber-500 fill-amber-500" />
                Direct Trains — {data.from_name} to {data.to_name}
              </h2>
              {data.direct_trains.length === 0 ? (
                <div className="p-6 rounded-xl border-2 border-dashed border-border text-center text-muted-foreground font-bold">
                  No direct trains found. Try the full search for transfer options.
                </div>
              ) : (
                <div className="space-y-2">
                  {data.direct_trains.map((t, i) => (
                    <TrainRow key={i} t={t} fromCode={data.from_code} toCode={data.to_code} date={selectedDate} />
                  ))}
                </div>
              )}
            </div>

            {/* Transfer routes */}
            {data.transfer_routes.length > 0 && (
              <div className="mb-8">
                <h2 className="text-xl font-black mb-4 flex items-center gap-2">
                  <RotateCcw className="w-5 h-5 text-blue-500" />
                  Routes via Transfer
                </h2>
                <div className="space-y-2">
                  {data.transfer_routes.map((tr, i) => (
                    <div key={i} className="flex items-center gap-3 p-4 rounded-xl border-2 border-border bg-card">
                      <Train className="w-5 h-5 text-blue-500 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="font-bold text-sm">{tr.train1} → <span className="text-primary font-black">{tr.hub}</span> → {tr.train2}</p>
                        <p className="text-xs text-muted-foreground">1 transfer · {tr.total_hrs}h total</p>
                      </div>
                      <Link
                        to={`/?from=${data.from_code}&to=${data.to_code}&date=${selectedDate}`}
                        className="px-3 py-1.5 rounded-lg bg-secondary text-sm font-bold hover:bg-primary/10 hover:text-primary transition-colors shrink-0"
                      >
                        Full Details
                      </Link>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* FAQ — Schema.org structured data  */}
            <div className="mb-8">
              <h2 className="text-xl font-black mb-4">Frequently Asked Questions</h2>
              <div className="space-y-2">
                {data.seo.faq.map((faq, i) => <FAQItem key={i} {...faq} />)}
              </div>
            </div>

            {/* Related routes */}
            <div className="bg-secondary/30 rounded-2xl p-5 border border-dashed border-border">
              <h3 className="font-black text-sm uppercase tracking-widest text-muted-foreground mb-3">Related Searches</h3>
              <div className="flex flex-wrap gap-2">
                {[
                  { label: `${data.to_name} → ${data.from_name}`, path: `/trains/${data.to_slug}/${data.from_slug}` },
                  { label: `Live status trains to ${data.to_name}`, path: `/track` },
                  { label: `${data.from_name} station board`, path: `/station/${data.from_code}` },
                  { label: `${data.to_name} station board`, path: `/station/${data.to_code}` },
                  { label: "PNR Status", path: "/pnr" },
                ].map((link, i) => (
                  <Link
                    key={i}
                    to={link.path}
                    className="px-3 py-1.5 rounded-full bg-card border border-border text-xs font-bold text-muted-foreground hover:text-primary hover:border-primary/40 transition-colors"
                  >
                    {link.label}
                  </Link>
                ))}
              </div>
            </div>
          </>
        )}
      </main>
      <Footer />
    </div>
  );
}

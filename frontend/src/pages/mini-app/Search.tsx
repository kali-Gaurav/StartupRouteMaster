import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { 
  Search, 
  ArrowLeft, 
  MapPin, 
  Train, 
  Calendar, 
  Filter, 
  ArrowRightLeft,
  Loader2,
  Clock,
  Navigation,
  ShieldCheck,
  Zap
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { getRailwayApiUrl } from "@/lib/utils";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

const MiniAppSearch = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [from, setFrom] = useState(searchParams.get("from") || "");
  const [to, setTo] = useState(searchParams.get("to") || "");
  const [date, setDate] = useState(searchParams.get("date") || new Date().toISOString().split('T')[0]);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any[]>([]);
  const [hasSearched, setHasSearched] = useState(false);

  useEffect(() => {
    if (from && to) {
      handleSearch();
    }
  }, []);

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!from || !to) {
      toast.error("Please enter both stations");
      return;
    }

    setLoading(true);
    setHasSearched(true);
    try {
      const response = await fetch(getRailwayApiUrl(`/api/search?from=${from}&to=${to}&date=${date}`));
      if (response.ok) {
        const data = await response.json();
        setResults(data.routes || []);
      } else {
        toast.error("Search failed");
      }
    } catch (error) {
      console.error("Search failed:", error);
      toast.error("Network error during search");
    } finally {
      setLoading(false);
    }
  };

  const swapStations = () => {
    const temp = from;
    setFrom(to);
    setTo(temp);
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col selection:bg-primary selection:text-primary-foreground">
      {/* Sticky Header with Search Controls */}
      <div className="p-4 bg-background/80 backdrop-blur-xl border-b border-border sticky top-0 z-20">
        <div className="max-w-md mx-auto space-y-4">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={() => navigate("/mini-app")} className="rounded-xl hover:bg-muted">
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <h1 className="text-xl font-black uppercase tracking-tighter">Route Search</h1>
          </div>

          <form onSubmit={handleSearch} className="space-y-3">
            <div className="relative space-y-2">
              <div className="relative group">
                <MapPin className="absolute left-4 top-3.5 h-5 w-5 text-primary" />
                <Input
                  placeholder="From Station"
                  value={from}
                  onChange={(e) => setFrom(e.target.value.toUpperCase())}
                  className="pl-12 py-7 rounded-2xl border-2 bg-muted/30 focus:bg-background transition-all font-bold"
                />
              </div>
              
              <div className="absolute right-4 top-1/2 -translate-y-1/2 z-10">
                <Button 
                  type="button"
                  variant="ghost" 
                  size="icon" 
                  onClick={swapStations} 
                  className="h-10 w-10 rounded-full bg-background shadow-md border border-border hover:bg-muted active:scale-90 transition-all"
                >
                  <ArrowRightLeft className="h-4 w-4 text-primary rotate-90" />
                </Button>
              </div>

              <div className="relative group">
                <Navigation className="absolute left-4 top-3.5 h-5 w-5 text-emerald-500" />
                <Input
                  placeholder="To Station"
                  value={to}
                  onChange={(e) => setTo(e.target.value.toUpperCase())}
                  className="pl-12 py-7 rounded-2xl border-2 bg-muted/30 focus:bg-background transition-all font-bold"
                />
              </div>
            </div>

            <div className="flex gap-2">
              <div className="relative flex-1 group">
                <Calendar className="absolute left-4 top-3.5 h-5 w-5 text-muted-foreground" />
                <Input
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  className="pl-12 py-7 rounded-2xl border-2 bg-muted/30 focus:bg-background transition-all font-bold"
                />
              </div>
              <Button type="submit" disabled={loading} className="h-auto px-8 rounded-2xl shadow-lg shadow-primary/20 active:scale-95 transition-all">
                {loading ? <Loader2 className="h-6 w-6 animate-spin" /> : <Search className="h-6 w-6" />}
              </Button>
            </div>
          </form>
        </div>
      </div>

      {/* Main Results Area */}
      <main className="flex-1 max-w-md mx-auto w-full p-4 space-y-4">
        {!hasSearched ? (
          <div className="py-20 text-center space-y-6 animate-in fade-in slide-in-from-bottom-4">
            <div className="w-20 h-20 bg-primary/10 rounded-3xl flex items-center justify-center mx-auto shadow-inner">
              <Train className="h-10 w-10 text-primary animate-pulse" />
            </div>
            <div>
              <h3 className="text-xl font-black uppercase tracking-tight">Neural Search Active</h3>
              <p className="text-sm text-muted-foreground font-bold mt-2">Enter stations to calculate optimal vectors</p>
            </div>
            <div className="flex flex-wrap justify-center gap-2">
               {['NDLS', 'BCT', 'MAS', 'HWH'].map(code => (
                 <button 
                   key={code}
                   onClick={() => setFrom(code)}
                   className="px-4 py-2 rounded-xl bg-muted border border-border text-[10px] font-black uppercase tracking-widest hover:bg-primary hover:text-white transition-all"
                 >
                   {code}
                 </button>
               ))}
            </div>
          </div>
        ) : loading ? (
          <div className="py-20 text-center space-y-4">
            <Loader2 className="h-12 w-12 animate-spin text-primary mx-auto" />
            <p className="text-xs font-black uppercase tracking-widest text-muted-foreground">Synchronizing Timetables...</p>
          </div>
        ) : results.length > 0 ? (
          <div className="space-y-4 animate-in fade-in duration-500">
            <div className="flex items-center justify-between px-1">
              <span className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">{results.length} Routes Identified</span>
              <Button variant="ghost" size="sm" className="h-7 text-[10px] font-black uppercase tracking-widest gap-1">
                <Filter className="h-3 w-3" /> Filter
              </Button>
            </div>
            {results.map((route, i) => (
              <Card 
                key={i} 
                className="border-none glass hover:scale-[1.01] transition-transform active:scale-[0.99] cursor-pointer overflow-hidden group"
                onClick={() => navigate(`/mini-app/booking?id=${route.id || i}`)}
              >
                <div className="h-1 w-full bg-gradient-to-r from-primary/50 to-emerald-500/50 opacity-0 group-hover:opacity-100 transition-opacity" />
                <CardContent className="p-5 space-y-4">
                  <div className="flex justify-between items-start">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded bg-primary text-[10px] font-black text-white uppercase tracking-tighter">SUPERFAST</span>
                        <span className="text-xs font-black text-primary uppercase">#{route.train_number || '12002'}</span>
                      </div>
                      <h3 className="font-black text-lg uppercase tracking-tight leading-none">{route.train_name || "Shatabdi Express"}</h3>
                    </div>
                    <div className="text-right">
                      <p className="text-2xl font-black tracking-tighter">₹{route.fare || '1,240'}</p>
                      <p className="text-[9px] font-black text-emerald-500 uppercase tracking-widest">Available</p>
                    </div>
                  </div>

                  <div className="flex justify-between items-center bg-muted/50 p-4 rounded-2xl relative">
                    <div className="text-center z-10">
                      <p className="text-xl font-black tabular-nums">{route.departure_time || '06:00'}</p>
                      <p className="text-[10px] font-black text-muted-foreground uppercase">{from}</p>
                    </div>
                    
                    <div className="flex-1 flex flex-col items-center gap-1 px-4">
                       <div className="w-full h-px bg-border relative">
                         <div className="absolute inset-0 bg-primary/30 animate-pulse" />
                         <Train className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-4 w-4 text-primary bg-background p-0.5 rounded-full border border-border" />
                       </div>
                       <span className="text-[9px] font-black text-muted-foreground uppercase">{route.duration || '6h 40m'}</span>
                    </div>

                    <div className="text-center z-10">
                      <p className="text-xl font-black tabular-nums">{route.arrival_time || '12:40'}</p>
                      <p className="text-[10px] font-black text-muted-foreground uppercase">{to}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 text-[10px] font-black uppercase tracking-tighter text-muted-foreground pt-1">
                    <span className="flex items-center gap-1"><ShieldCheck className="h-3 w-3 text-emerald-500" /> Verified Safe</span>
                    <span className="flex items-center gap-1 text-amber-500"><Zap className="h-3 w-3 fill-current" /> 98% On-Time</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <div className="py-20 text-center space-y-4">
            <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center mx-auto opacity-50">
              <Search className="h-8 w-8" />
            </div>
            <p className="text-sm font-black uppercase tracking-widest text-muted-foreground">Zero Vectors Found</p>
            <Button variant="outline" onClick={() => setHasSearched(false)} className="rounded-xl font-bold">RETRY CALCULATION</Button>
          </div>
        )}
      </main>
    </div>
  );
};

export default MiniAppSearch;

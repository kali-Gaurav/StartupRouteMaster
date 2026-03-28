import React, { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Train, ArrowRight, ExternalLink, Info, ShieldCheck, Clock } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { getStationByCode } from "@/data/stations";
import { cn } from "@/lib/utils";

const IrctcRedirect = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [countdown, setCountdown] = useState(5);

  const trainNumber = searchParams.get("train") || "";
  const fromCode = searchParams.get("from") || "";
  const toCode = searchParams.get("to") || "";
  const date = searchParams.get("date") || "";

  const fromStation = getStationByCode(fromCode);
  const toStation = getStationByCode(toCode);

  const irctcUrl = `https://www.irctc.co.in/nget/train-search?fromStation=${fromCode}&toStation=${toCode}&journeyDate=${date.replace(/-/g, "")}`;

  useEffect(() => {
    if (!trainNumber || !fromCode || !toCode) {
      navigate("/");
      return;
    }

    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          window.location.href = irctcUrl;
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [trainNumber, fromCode, toCode, navigate, irctcUrl]);

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar />
      
      <main className="flex-1 container mx-auto px-4 py-12 flex items-center justify-center">
        <div className="max-w-md w-full bg-card rounded-3xl border-2 border-border shadow-xl overflow-hidden animate-in zoom-in duration-500">
          <div className="bg-primary/10 p-8 text-center border-b border-border">
            <div className="w-20 h-20 bg-primary/20 rounded-full flex items-center justify-center mx-auto mb-6 animate-pulse">
              <Train className="w-10 h-10 text-primary" />
            </div>
            <h1 className="text-2xl font-bold text-foreground mb-2">Redirecting to IRCTC</h1>
            <p className="text-muted-foreground text-sm">
              We're preparing your search details for a seamless booking experience.
            </p>
          </div>

          <div className="p-8 space-y-6">
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 rounded-2xl bg-secondary/50 border border-border">
                <div className="text-center flex-1">
                  <div className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1">From</div>
                  <div className="text-lg font-bold text-foreground">{fromCode}</div>
                  <div className="text-[10px] text-muted-foreground truncate max-w-[100px] mx-auto">
                    {fromStation?.name || "Station"}
                  </div>
                </div>
                <ArrowRight className="text-primary w-5 h-5 mx-2" />
                <div className="text-center flex-1">
                  <div className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1">To</div>
                  <div className="text-lg font-bold text-foreground">{toCode}</div>
                  <div className="text-[10px] text-muted-foreground truncate max-w-[100px] mx-auto">
                    {toStation?.name || "Station"}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 rounded-2xl bg-secondary/50 border border-border text-center">
                  <div className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1">Train</div>
                  <div className="text-lg font-bold text-foreground">{trainNumber}</div>
                </div>
                <div className="p-4 rounded-2xl bg-secondary/50 border border-border text-center">
                  <div className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1">Date</div>
                  <div className="text-lg font-bold text-foreground">{date}</div>
                </div>
              </div>
            </div>

            <div className="space-y-3">
              <a 
                href={irctcUrl}
                className="w-full py-4 px-6 rounded-xl bg-primary text-primary-foreground font-bold flex items-center justify-center gap-2 hover:opacity-90 transition-all shadow-lg shadow-primary/20"
              >
                Continue to IRCTC Now
                <ExternalLink size={18} />
              </a>
              <p className="text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                <Clock size={12} />
                Redirecting automatically in {countdown}s...
              </p>
            </div>

            <div className="pt-4 border-t border-border">
              <div className="flex items-start gap-3 p-3 rounded-xl bg-emerald-500/5 border border-emerald-500/10">
                <ShieldCheck className="w-5 h-5 text-emerald-500 shrink-0" />
                <div className="text-[11px] text-emerald-700 dark:text-emerald-400 leading-relaxed">
                  <strong>Pro Tip:</strong> After booking, come back and enter your 10-digit PNR in RouteMaster to enable <strong>Satellite SOS Tracking</strong> and delay alerts.
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
};

export default IrctcRedirect;

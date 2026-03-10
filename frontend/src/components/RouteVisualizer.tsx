import { ArrowRight, Train } from "lucide-react";
import { cn } from "@/lib/utils";

interface RouteVisualizerProps {
  source: string;
  destination: string;
  transfers?: string[];
  className?: string;
}

export function RouteVisualizer({ source, destination, transfers = [], className }: RouteVisualizerProps) {
  const allStops = [source, ...transfers, destination];
  
  return (
    <div className={cn("bg-white dark:bg-muted border border-border rounded-2xl p-4 shadow-sm w-full", className)}>
      <div className="flex items-center gap-2 text-primary font-bold text-xs mb-4 uppercase tracking-widest">
        <Train className="w-3 h-3" />
        Route Summary
      </div>
      
      <div className="relative flex justify-between items-center px-2">
        {/* Connection Line */}
        <div className="absolute top-1/2 left-4 right-4 h-0.5 bg-muted-foreground/20 -translate-y-1/2" />
        
        {allStops.map((stop, i) => (
          <div key={i} className="relative z-10 flex flex-col items-center gap-1.5">
            <div className={cn(
              "w-3 h-3 rounded-full border-2 border-white dark:border-muted shadow-sm",
              i === 0 || i === allStops.length - 1 ? "bg-primary scale-125" : "bg-muted-foreground/40"
            )} />
            <span className={cn(
              "text-[10px] font-black uppercase tracking-tighter",
              i === 0 || i === allStops.length - 1 ? "text-primary" : "text-muted-foreground"
            )}>
              {stop}
            </span>
          </div>
        ))}
      </div>
      
      <div className="mt-4 pt-3 border-t border-border flex justify-between items-center">
        <div className="text-[10px] font-medium text-muted-foreground">
          {transfers.length > 0 ? `${transfers.length} Transfer(s)` : "Direct Route"}
        </div>
        <div className="flex items-center gap-1 text-[10px] font-black text-primary uppercase">
          {source} <ArrowRight className="w-2 h-2" /> {destination}
        </div>
      </div>
    </div>
  );
}

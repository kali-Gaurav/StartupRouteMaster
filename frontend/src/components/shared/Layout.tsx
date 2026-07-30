import { ReactNode } from "react";
import { Train, ShieldCheck } from "lucide-react";

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col bg-background selection:bg-primary/20">
      <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/60 backdrop-blur-xl">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2 group cursor-pointer">
            <div className="bg-primary/10 p-2 rounded-xl text-primary group-hover:scale-105 transition-transform">
              <Train className="w-5 h-5" />
            </div>
            <span className="font-bold text-xl tracking-tight">RouteMaster</span>
          </div>
          
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground bg-secondary/50 px-3 py-1.5 rounded-full">
            <ShieldCheck className="w-4 h-4 text-emerald-500" />
            <span>Escrow Protected</span>
          </div>
        </div>
      </header>

      <main className="flex-1 flex flex-col relative overflow-hidden">
        {/* Decorative background blur */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-3xl h-full pointer-events-none overflow-hidden z-0">
          <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-primary/5 rounded-full blur-[100px]" />
          <div className="absolute bottom-[20%] right-[-10%] w-[40%] h-[40%] bg-accent/5 rounded-full blur-[100px]" />
        </div>
        
        <div className="relative z-10 flex-1 flex flex-col container mx-auto px-4 py-8">
          {children}
        </div>
      </main>

      <footer className="py-6 border-t border-border/50 bg-card/30">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          <p>© {new Date().getFullYear()} RouteMaster AI. All rights reserved.</p>
          <p className="mt-1 opacity-70">Zero-Gateway UPI Escrow Pipeline</p>
        </div>
      </footer>
    </div>
  );
}

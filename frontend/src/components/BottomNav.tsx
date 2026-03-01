import { Home, ShieldAlert, LayoutDashboard, Ticket, MessageCircle } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";

const navItems = [
  { icon: Home, label: "Home", path: "/" },
  { icon: ShieldAlert, label: "SOS", path: "/sos", color: "text-red-500" },
  { icon: LayoutDashboard, label: "Stats", path: "/dashboard" },
  { icon: Ticket, label: "Bookings", path: "/bookings" },
];

export function BottomNav() {
  const location = useLocation();

  return (
    <div className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-lg border-t border-border px-6 py-3 pb-safe flex items-center justify-between shadow-[0_-4px_12px_rgba(0,0,0,0.05)]">
      {navItems.map((item) => {
        const isActive = location.pathname === item.path;
        const Icon = item.icon;
        
        return (
          <Link
            key={item.path}
            to={item.path}
            className={cn(
              "flex flex-col items-center gap-1 transition-all duration-200",
              isActive ? (item.color || "text-primary scale-110") : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon className={cn("w-6 h-6", isActive && "stroke-[2.5px]")} />
            <span className={cn("text-[10px] font-bold uppercase tracking-tighter", isActive ? "opacity-100" : "opacity-60")}>
              {item.label}
            </span>
          </Link>
        );
      })}
      
      <a
        href="https://t.me/RoutemasternagarindustrisBot"
        target="_blank"
        rel="noopener noreferrer"
        className="flex flex-col items-center gap-1 text-primary opacity-60 hover:opacity-100 transition-all"
      >
        <MessageCircle className="w-6 h-6" />
        <span className="text-[10px] font-bold uppercase tracking-tighter">AI</span>
      </a>
    </div>
  );
}

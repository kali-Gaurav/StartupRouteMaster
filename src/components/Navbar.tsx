import { Train, Menu, X, ShieldAlert, LayoutDashboard, MessageCircle, Ticket, Palette } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { prefetchBookings } from "@/lib/queryInvalidation";
import { THEME_IDS, THEME_LABELS, type ThemeId } from "@/lib/themes/tokens";

const TELEGRAM_BOT_URL = "https://t.me/RoutemasternagarindustrisBot";

export function Navbar() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [themeOpen, setThemeOpen] = useState(false);
  const themeRef = useRef<HTMLDivElement>(null);
  const { isAuthenticated } = useAuth();
  const { theme, setTheme, rotationDisabled, setRotationDisabled } = useTheme();

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (themeRef.current && !themeRef.current.contains(e.target as Node)) setThemeOpen(false);
    };
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, []);

  const handleBookingsHover = () => {
    if (isAuthenticated) prefetchBookings();
  };

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 glass">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <a href="/" className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl hero-gradient flex items-center justify-center">
              <Train className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-foreground">
              Pareto<span className="text-gradient">Route</span>
            </span>
          </a>

          {/* Desktop Nav */}
          <div className="hidden md:flex items-center gap-8">
            <a href="/" className="text-muted-foreground hover:text-foreground transition-colors">
              Trains
            </a>
            <a href="/sos" className="flex items-center gap-1.5 text-red-600 hover:text-red-700 font-medium">
              <ShieldAlert className="w-4 h-4" />
              SOS
            </a>
            <a href="/dashboard" className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors">
              <LayoutDashboard className="w-4 h-4" />
              Dashboard
            </a>
            <a
              href="/bookings"
              className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors"
              onMouseEnter={handleBookingsHover}
              onFocus={handleBookingsHover}
            >
              <Ticket className="w-4 h-4" />
              My Bookings
            </a>
            <a
              href={TELEGRAM_BOT_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 font-medium transition-colors"
            >
              <MessageCircle className="w-4 h-4" />
              Use in Telegram
            </a>
            <div className="relative" ref={themeRef}>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setThemeOpen((o) => !o); }}
                className="flex items-center gap-1.5 p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                title="Theme"
              >
                <Palette className="w-4 h-4" />
              </button>
              {themeOpen && (
                <div className="absolute right-0 top-full mt-1 py-2 w-52 rounded-lg border border-border bg-card shadow-lg z-50 animate-fade-in">
                  <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">Theme</div>
                  {THEME_IDS.map((id) => (
                    <button
                      key={id}
                      type="button"
                      onClick={() => { setTheme(id as ThemeId); setRotationDisabled(true); setThemeOpen(false); }}
                      className={`w-full text-left px-3 py-2 text-sm ${theme === id ? "bg-primary/10 text-primary font-medium" : "text-foreground hover:bg-muted"}`}
                    >
                      {THEME_LABELS[id]}
                    </button>
                  ))}
                  <label className="flex items-center gap-2 px-3 py-2 mt-1 border-t border-border cursor-pointer text-sm text-foreground">
                    <input
                      type="checkbox"
                      checked={!rotationDisabled}
                      onChange={(e) => setRotationDisabled(!e.target.checked)}
                    />
                    Rotate hourly
                  </label>
                </div>
              )}
            </div>
          </div>

          {/* Mobile Menu Toggle */}
          <button
            className="md:hidden p-2"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
          >
            {isMenuOpen ? (
              <X className="w-6 h-6 text-foreground" />
            ) : (
              <Menu className="w-6 h-6 text-foreground" />
            )}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      {isMenuOpen && (
        <div className="md:hidden border-t border-border bg-background animate-fade-in">
          <div className="container mx-auto px-4 py-4 space-y-4">
            <a href="/" className="block py-2 text-foreground">Trains</a>
            <a href="/sos" className="flex items-center gap-2 py-2 text-red-600 font-medium">
              <ShieldAlert className="w-4 h-4" /> SOS
            </a>
            <a href="/dashboard" className="flex items-center gap-2 py-2 text-foreground">
              <LayoutDashboard className="w-4 h-4" /> Dashboard
            </a>
            <a href="/bookings" className="flex items-center gap-2 py-2 text-foreground" onFocus={handleBookingsHover} onMouseEnter={handleBookingsHover}>
              <Ticket className="w-4 h-4" /> My Bookings
            </a>
            <a href={TELEGRAM_BOT_URL} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 py-2 text-primary font-medium">
              <MessageCircle className="w-4 h-4" /> Use in Telegram
            </a>
            <div className="pt-2 border-t border-border">
              <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Theme</div>
              <div className="flex flex-wrap gap-2">
                {THEME_IDS.map((id) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => { setTheme(id as ThemeId); setRotationDisabled(true); }}
                    className={`px-3 py-1.5 rounded-lg text-sm ${theme === id ? "bg-primary text-primary-foreground" : "bg-muted text-foreground"}`}
                  >
                    {THEME_LABELS[id]}
                  </button>
                ))}
              </div>
              <label className="flex items-center gap-2 mt-2 text-sm text-foreground">
                <input
                  type="checkbox"
                  checked={!rotationDisabled}
                  onChange={(e) => setRotationDisabled(!e.target.checked)}
                />
                Rotate theme hourly
              </label>
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}

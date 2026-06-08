import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { 
  Heart, 
  ArrowLeft, 
  Trash2, 
  Train, 
  ChevronRight,
  Clock,
  ShieldCheck,
  Star
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { storageService } from "@/services/storageService";
import { useTelegramWebApp } from "@/hooks/useTelegramWebApp";

const MiniAppSaved = () => {
  const navigate = useNavigate();
  const { webApp, showBackButton, hapticFeedback } = useTelegramWebApp();
  const [favorites, setFavorites] = useState<any[]>([]);

  useEffect(() => {
    loadFavorites();
    const hide = showBackButton(() => navigate("/mini-app"));
    return hide;
  }, [showBackButton, navigate]);

  const loadFavorites = async () => {
    try {
      const data = await storageService.getFavorites();
      setFavorites(data || []);
    } catch (e) {
      console.error(e);
    }
  };

  const removeFavorite = async (id: string) => {
    hapticFeedback?.impactOccurred("medium");
    await storageService.removeFavorite(id);
    loadFavorites();
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col selection:bg-primary selection:text-primary-foreground">
      <div className="p-4 border-b border-border sticky top-0 z-20 bg-background/80 backdrop-blur-xl">
        <div className="max-w-md mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={() => navigate("/mini-app")} className="rounded-xl lg:hidden">
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <h1 className="text-xl font-black uppercase tracking-tighter">Saved Vectors</h1>
          </div>
          <Badge variant="outline" className="font-black text-[10px]">{favorites.length} ROUTES</Badge>
        </div>
      </div>

      <main className="flex-1 max-w-md mx-auto w-full p-4 space-y-4">
        {favorites.length === 0 ? (
          <div className="py-20 text-center space-y-6">
            <div className="w-20 h-20 bg-muted rounded-full flex items-center justify-center mx-auto">
              <Heart className="h-10 w-10 text-muted-foreground opacity-20" />
            </div>
            <div>
              <h3 className="text-xl font-black uppercase tracking-tight opacity-40">Watchlist Empty</h3>
              <p className="text-sm text-muted-foreground font-bold mt-2 uppercase tracking-tighter">Your preferred corridors will appear here</p>
            </div>
            <Button onClick={() => navigate("/mini-app/search")} className="rounded-xl font-black uppercase tracking-widest text-[10px] px-8 h-12">Initialize Search</Button>
          </div>
        ) : (
          <div className="space-y-3 animate-in fade-in duration-500">
            {favorites.map((fav) => (
              <Card 
                key={fav.id} 
                className="border-none glass hover:scale-[1.01] transition-transform active:scale-[0.99] cursor-pointer overflow-hidden group"
              >
                <CardContent className="p-5 flex items-center justify-between gap-4">
                  <div className="flex items-center gap-4 flex-1">
                    <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center shrink-0 shadow-inner">
                      <Train className="h-6 w-6 text-primary" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <p className="font-black text-foreground uppercase tracking-tight truncate">{fav.source} → {fav.destination}</p>
                      </div>
                      <div className="flex items-center gap-3 text-[10px] font-bold text-muted-foreground uppercase opacity-60">
                        <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> DAILY</span>
                        <span className="flex items-center gap-1"><ShieldCheck className="w-3 h-3 text-emerald-500" /> SECURE</span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      className="rounded-xl text-muted-foreground hover:text-red-500 hover:bg-red-500/10"
                      onClick={(e) => {
                        e.stopPropagation();
                        removeFavorite(fav.id);
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                    <ChevronRight className="h-5 w-5 text-muted-foreground opacity-20 group-hover:opacity-100 transition-opacity" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {favorites.length > 0 && (
          <div className="pt-6 pb-10">
            <Card className="border-none glass bg-blue-500/5">
              <CardContent className="p-6 text-center">
                <Star className="h-6 w-6 text-blue-500 mx-auto mb-3 animate-pulse" />
                <h4 className="text-sm font-black uppercase tracking-tight">Neural Sync</h4>
                <p className="text-[10px] font-bold text-muted-foreground uppercase mt-1 leading-relaxed">Your watchlist is automatically synchronized across all authorized nodes.</p>
              </CardContent>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
};

export default MiniAppSaved;

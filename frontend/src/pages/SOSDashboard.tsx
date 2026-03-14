import { useState, useEffect } from "react";
import { 
  ShieldAlert, 
  MapPin, 
  Clock, 
  User, 
  Phone, 
  CheckCircle, 
  AlertTriangle,
  ExternalLink,
  MessageSquare,
  Zap,
  Activity,
  Navigation,
  Loader2,
  RefreshCw,
  Search,
  MoreVertical
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

// Mock Active SOS Events for Operator View
const MOCK_EVENTS = [
  {
    id: "SOS-9921",
    name: "Rajesh Kumar",
    phone: "+91 98765 43210",
    train: "12002 - Shatabdi Express",
    pnr: "4421908821",
    lat: 28.6139,
    lng: 77.2090,
    status: "active",
    priority: "high",
    triggered_at: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
    battery: 0.85
  },
  {
    id: "SOS-9925",
    name: "Priya Sharma",
    phone: "+91 91234 56789",
    train: "12951 - Rajdhani Exp",
    pnr: "2281773641",
    lat: 19.0760,
    lng: 72.8777,
    status: "active",
    priority: "standard",
    triggered_at: new Date(Date.now() - 1000 * 60 * 12).toISOString(),
    battery: 0.42
  }
];

const SOSDashboard = () => {
  const [events, setEvents] = useState(MOCK_EVENTS);
  const [selectedEvent, setSelectedEvent] = useState<any>(MOCK_EVENTS[0]);
  const [loading, setLoading] = useState(false);

  const getPriorityColor = (p: string) => {
    switch (p) {
      case 'high': return "bg-red-500 text-white shadow-lg shadow-red-500/20";
      case 'standard': return "bg-amber-500 text-white shadow-lg shadow-amber-500/20";
      default: return "bg-muted text-muted-foreground";
    }
  };

  const handleResolve = (id: string) => {
    setEvents(events.filter(e => e.id !== id));
    if (selectedEvent?.id === id) setSelectedEvent(null);
    toast.success(`Event ${id} marked as resolved`);
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col selection:bg-primary selection:text-primary-foreground font-sans">
      {/* Header */}
      <header className="p-4 border-b border-border bg-background/80 backdrop-blur-xl sticky top-0 z-30 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 bg-red-600 rounded-xl flex items-center justify-center shadow-lg shadow-red-600/20">
            <ShieldAlert className="w-6 h-6 text-white animate-pulse" />
          </div>
          <div>
            <h1 className="text-xl font-black uppercase tracking-tighter leading-none">SafeGuard Ops</h1>
            <p className="text-[10px] font-black uppercase text-muted-foreground tracking-widest mt-1 opacity-60">Terminal: DL_HQ_CENTRAL</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-muted rounded-xl border border-border">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-[10px] font-black uppercase tracking-widest">Network Secure</span>
          </div>
          <Button variant="ghost" size="icon" className="rounded-xl"><RefreshCw className="h-5 w-5" /></Button>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar: Event Feed */}
        <aside className="w-full md:w-80 lg:w-96 border-r border-border bg-muted/30 overflow-y-auto flex flex-col shrink-0">
          <div className="p-4 border-b border-border space-y-4">
            <div className="relative group">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
              <Input placeholder="Search PNR or Entity..." className="pl-10 h-10 rounded-xl bg-background border-2 border-transparent focus:border-primary/20" />
            </div>
            <div className="flex justify-between items-center px-1">
              <span className="text-[10px] font-black uppercase tracking-[0.2em] text-muted-foreground">Live Feed ({events.length})</span>
              <Badge className="bg-red-500/10 text-red-500 border-none text-[9px] font-black">ACTIVE</Badge>
            </div>
          </div>

          <div className="flex-1 divide-y divide-border">
            {events.map((e) => (
              <div 
                key={e.id}
                onClick={() => setSelectedEvent(e)}
                className={cn(
                  "p-5 cursor-pointer transition-all relative group",
                  selectedEvent?.id === e.id ? "bg-background border-l-4 border-l-red-600" : "hover:bg-background/50"
                )}
              >
                <div className="flex justify-between items-start mb-3">
                  <Badge className={cn("text-[8px] font-black uppercase tracking-widest border-none px-2", getPriorityColor(e.priority))}>
                    {e.priority}
                  </Badge>
                  <span className="text-[9px] font-mono text-muted-foreground opacity-60">
                    {new Date(e.triggered_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
                <h3 className="text-sm font-black uppercase tracking-tight truncate">{e.name}</h3>
                <p className="text-[10px] font-bold text-muted-foreground uppercase mt-1 opacity-60">{e.train}</p>
                <div className="flex items-center gap-2 mt-4">
                  <div className="w-full h-1 bg-muted rounded-full overflow-hidden">
                    <div className={cn("h-full rounded-full transition-all duration-1000", e.battery < 0.3 ? "bg-red-500" : "bg-emerald-500")} style={{ width: `${e.battery * 100}%` }} />
                  </div>
                  <span className="text-[8px] font-black text-muted-foreground">{Math.round(e.battery * 100)}%</span>
                </div>
              </div>
            ))}
          </div>
        </aside>

        {/* Main Console: Map + Intelligence */}
        <main className="flex-1 bg-background overflow-y-auto p-6 space-y-6">
          {selectedEvent ? (
            <div className="max-w-5xl mx-auto space-y-6 animate-in fade-in duration-500">
              {/* Event Header Detail */}
              <div className="flex flex-wrap justify-between items-end gap-6 border-b border-border pb-6">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-[10px] font-black uppercase text-red-600 border-red-600/20 bg-red-600/5">INCIDENT_ID: {selectedEvent.id}</Badge>
                    <Badge variant="outline" className="text-[10px] font-black uppercase">PNR: {selectedEvent.pnr}</Badge>
                  </div>
                  <h2 className="text-4xl font-black uppercase tracking-tighter">{selectedEvent.name}</h2>
                  <div className="flex items-center gap-4 text-xs font-bold text-muted-foreground uppercase tracking-widest">
                    <span className="flex items-center gap-1.5"><Phone className="w-3.5 h-3.5" /> {selectedEvent.phone}</span>
                    <span className="w-1.5 h-1.5 rounded-full bg-border" />
                    <span className="flex items-center gap-1.5 text-primary"><Train className="w-3.5 h-3.5" /> {selectedEvent.train}</span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" className="rounded-xl font-black uppercase text-[10px] tracking-widest gap-2 border-2">
                    <MessageSquare className="w-4 h-4" /> Open Comms
                  </Button>
                  <Button className="bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-black uppercase text-[10px] tracking-widest gap-2" onClick={() => handleResolve(selectedEvent.id)}>
                    <CheckCircle className="w-4 h-4" /> Resolve Case
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Map Mockup */}
                <Card className="lg:col-span-2 border-none glass overflow-hidden relative min-h-[450px] shadow-2xl">
                  <div className="absolute inset-0 bg-muted/20 flex flex-col items-center justify-center p-10 text-center space-y-4">
                    <div className="relative">
                      <div className="w-20 h-20 bg-red-600/10 rounded-full flex items-center justify-center animate-ping absolute inset-0" />
                      <div className="w-20 h-20 bg-background border-2 border-border rounded-full flex items-center justify-center relative shadow-xl">
                        <MapPin className="w-10 h-10 text-red-600" />
                      </div>
                    </div>
                    <div>
                      <h4 className="text-xl font-black uppercase tracking-tight">Active GPS Uplink</h4>
                      <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest mt-1">LAT: {selectedEvent.lat} | LNG: {selectedEvent.lng}</p>
                    </div>
                    <Button variant="outline" className="rounded-xl font-black uppercase text-[10px] bg-background">Launch External Map</Button>
                  </div>
                  <div className="absolute bottom-4 left-4 bg-background/90 backdrop-blur-md p-3 rounded-xl border border-border shadow-lg">
                    <p className="text-[10px] font-black uppercase tracking-widest text-primary flex items-center gap-2">
                      <Navigation className="w-3 h-3" /> PRECISION_RADIUS: 5M
                    </p>
                  </div>
                </Card>

                {/* Intelligence Panel */}
                <div className="space-y-6">
                  <Card className="border-none glass bg-blue-500/5">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-blue-600 flex items-center gap-2">
                        <Activity className="w-4 h-4" /> Neural Analysis
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="p-3 bg-background rounded-xl border border-border space-y-1">
                        <span className="text-[9px] font-black uppercase text-muted-foreground">Threat Level</span>
                        <div className="flex justify-between items-center">
                          <span className="text-sm font-black text-amber-500 uppercase">ELEVATED</span>
                          <Zap className="w-4 h-4 text-amber-500 fill-current" />
                        </div>
                      </div>
                      <p className="text-[10px] font-bold text-muted-foreground leading-relaxed uppercase">
                        AI detected abnormal kinetic pattern matching "Rapid Deceleration". Passenger might be in distress or medical emergency.
                      </p>
                    </CardContent>
                  </Card>

                  <Card className="border-none glass">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-foreground flex items-center gap-2">
                        <User className="w-4 h-4" /> Emergency Contacts
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {[1, 2].map(i => (
                        <div key={i} className="p-3 bg-muted/50 rounded-xl flex items-center justify-between group">
                          <div>
                            <p className="text-xs font-black uppercase tracking-tight">Kin Member {i}</p>
                            <p className="text-[10px] font-bold text-muted-foreground">+91 99000 88776</p>
                          </div>
                          <Button variant="ghost" size="icon" className="rounded-lg h-8 w-8 hover:bg-emerald-500/10 hover:text-emerald-500"><Phone className="w-4 h-4" /></Button>
                        </div>
                      ))}
                    </CardContent>
                  </Card>

                  <div className="bg-red-600 rounded-2xl p-5 text-white shadow-xl shadow-red-600/20 relative overflow-hidden">
                    <div className="relative z-10">
                      <h4 className="font-black uppercase text-xs tracking-widest mb-1">Station Dispatch</h4>
                      <p className="text-[10px] font-bold text-red-100 uppercase mb-4">Nearest: KOTA JUNCTION (RPF)</p>
                      <Button className="w-full bg-white text-red-600 font-black uppercase text-[10px] tracking-widest rounded-xl h-10 hover:bg-red-50">INITIALIZE RPF DISPATCH</Button>
                    </div>
                    <ShieldAlert className="absolute right-[-10px] bottom-[-10px] w-24 h-24 text-white/10" />
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center space-y-6">
              <div className="w-24 h-24 bg-muted rounded-full flex items-center justify-center">
                <CheckCircle className="w-12 h-12 text-muted-foreground opacity-20" />
              </div>
              <div>
                <h3 className="text-2xl font-black uppercase tracking-tighter opacity-20">Select Incident Terminal</h3>
                <p className="text-sm text-muted-foreground font-bold uppercase tracking-widest mt-2 opacity-20">Awaiting distress signal synchronization...</p>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export default SOSDashboard;

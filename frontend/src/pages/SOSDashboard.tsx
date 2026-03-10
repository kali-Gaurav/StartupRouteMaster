import { useState, useEffect, useRef } from "react";
import {
  ShieldAlert,
  Activity,
  MapPin,
  PhoneCall,
  Siren,
  Users,
  CheckCircle,
  AlertTriangle,
  MessageCircle,
  Send
} from "lucide-react";
import { cn } from "@/lib/utils";
import { LiveIncidentMap } from "@/components/LiveIncidentMap";

// Mock data structure based on the new 50-task pipeline
interface SOSIncident {
  id: string;
  userId: string;
  name: string;
  phone: string;
  lat: number;
  lng: number;
  status: "new" | "active" | "responding" | "resolved" | "inactive";
  priority: "high" | "critical" | "medium";
  category: "medical" | "security" | "derailment" | "unknown";
  triggeredAt: string;
  batteryLevel: number;
  networkStrength: string;
  trainNo?: string;
  coach?: string;
  isCovert?: boolean;
  chatHistory?: { role: string; content: string; timestamp: string }[];
  active_participants?: string[];
  nearestAuthority?: {
    name: string;
    type: string;
    contact_number: string;
    distance_km: number;
    eta_mins: number;
  };
}

export default function SOSDashboard() {
  const [incidents, setIncidents] = useState<SOSIncident[]>([
    {
      id: "sos-1234",
      userId: "u-998",
      name: "Aditi Sharma",
      phone: "+91 98765 43210",
      lat: 28.6428,
      lng: 77.2190,
      status: "active",
      priority: "critical",
      category: "security",
      triggeredAt: new Date(Date.now() - 1000 * 60 * 2).toISOString(),
      batteryLevel: 24,
      networkStrength: "Weak (Edge)",
      trainNo: "12952",
      coach: "S4",
      chatHistory: [
        { role: "user", content: "Hi, I feel unsafe", timestamp: "22:15" },
        { role: "assistant", content: "I'm here. What's happening?", timestamp: "22:15" },
        { role: "user", content: "Someone is following me in coach S4", timestamp: "22:16" }
      ],
      nearestAuthority: {
        name: "New Delhi RPF Post",
        type: "RPF",
        contact_number: "+91-11-23363322",
        distance_km: 0.12,
        eta_mins: 2
      }
    },
    {
      id: "sos-5678",
      userId: "u-112",
      name: "Rahul Verma",
      phone: "+91 91234 56789",
      lat: 19.0760,
      lng: 72.8777,
      status: "new",
      priority: "high",
      category: "medical",
      triggeredAt: new Date(Date.now() - 1000 * 30).toISOString(),
      batteryLevel: 85,
      networkStrength: "Strong (4G)",
      trainNo: "12009",
      coach: "C2",
      nearestAuthority: {
        name: "Wockhardt Hospital",
        type: "HOSPITAL",
        contact_number: "+91-22-102",
        distance_km: 1.5,
        eta_mins: 10
      }
    }
  ]);

  const [selectedIncident, setSelectedIncident] = useState<SOSIncident | null>(incidents[0]);
  const [adminMessage, setAdminMessage] = useState("");
  const [liveChat, setLiveChat] = useState<any[]>([]);
  const chatWs = useRef<WebSocket | null>(null);

  // 1. Establish Secure Chat Connection
  useEffect(() => {
    if (!selectedIncident) return;

    const wsUrl = `ws://${window.location.hostname}:8000/api/v2/ws/sos/chat/${selectedIncident.id}`;
    chatWs.current = new WebSocket(wsUrl);

    chatWs.current.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === "admin_chat") {
        setLiveChat(prev => [...prev, payload.data]);
      }
    };

    return () => {
      chatWs.current?.close();
      setLiveChat([]);
    };
  }, [selectedIncident]);

  const sendAdminMessage = () => {
    if (!adminMessage.trim() || !chatWs.current) return;
    
    chatWs.current.send(JSON.stringify({
      sender: "OPS_ADMIN",
      message: adminMessage
    }));
    
    setAdminMessage("");
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "new": return "bg-red-600 text-white animate-pulse";
      case "active": return "bg-orange-500 text-white";
      case "responding": return "bg-blue-500 text-white";
      case "resolved": return "bg-green-500 text-white";
      default: return "bg-gray-500 text-white";
    }
  };

  const updateStatus = (id: string, newStatus: any) => {
    setIncidents(prev => prev.map(i => i.id === id ? { ...i, status: newStatus } : i));
    if (selectedIncident?.id === id) {
      setSelectedIncident(prev => prev ? { ...prev, status: newStatus } : null);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col md:flex-row font-sans">
      
      {/* LEFT PANEL: Incident Queue */}
      <div className="w-full md:w-1/3 lg:w-1/4 border-r border-border bg-muted/30 flex flex-col h-screen overflow-hidden">
        <div className="p-4 border-b border-border bg-white dark:bg-muted flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-2 text-red-600 font-black tracking-tight">
            <Siren className="w-6 h-6 animate-pulse" />
            <span>OPS COMMAND</span>
          </div>
          <div className="bg-red-100 text-red-700 text-xs font-bold px-2 py-1 rounded-full">
            {incidents.filter(i => i.status === 'new' || i.status === 'active').length} ACTIVE
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
          {incidents.map(incident => (
            <button
              key={incident.id}
              onClick={() => setSelectedIncident(incident)}
              className={cn(
                "w-full text-left p-4 rounded-xl border transition-all duration-200",
                selectedIncident?.id === incident.id 
                  ? "bg-white dark:bg-muted border-primary shadow-md scale-[1.02]" 
                  : "bg-white/50 dark:bg-muted/50 border-border hover:border-primary/50"
              )}
            >
              <div className="flex justify-between items-start mb-2">
                <span className={cn("text-[10px] font-black uppercase px-2 py-0.5 rounded shadow-sm", getStatusColor(incident.status))}>
                  {incident.status}
                </span>
                <span className="text-xs text-muted-foreground font-mono">
                  {new Date(incident.triggeredAt).toLocaleTimeString()}
                </span>
              </div>
              <div className="font-bold text-sm truncate">{incident.name}</div>
              <div className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                <MapPin className="w-3 h-3" /> Train {incident.trainNo} • {incident.coach}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* RIGHT PANEL: Live Telemetry & Control */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden bg-muted/10">
        {selectedIncident ? (
          <>
            {/* Header */}
            <div className="p-6 border-b border-border bg-white dark:bg-muted shadow-sm flex items-center justify-between">
              <div className="flex items-center gap-4">
                {selectedIncident.isCovert && (
                    <div className="flex items-center gap-2 bg-slate-900 text-white px-3 py-1.5 rounded-lg animate-pulse border border-primary/50">
                        <ShieldAlert className="w-4 h-4 text-primary" />
                        <span className="text-xs font-black tracking-widest uppercase">Silent Intervention</span>
                    </div>
                )}
                <div>
                  <h1 className="text-2xl font-black">{selectedIncident.name}</h1>
                  <p className="text-sm text-muted-foreground flex items-center gap-2 mt-1">
                    <PhoneCall className="w-4 h-4" /> {selectedIncident.phone}
                    <span className="opacity-50">|</span>
                    ID: <span className="font-mono">{selectedIncident.id}</span>
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <button 
                  onClick={() => updateStatus(selectedIncident.id, 'responding')}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-bold text-sm transition-colors shadow-sm"
                >
                  Mark Responding
                </button>
                <button 
                  onClick={() => updateStatus(selectedIncident.id, 'resolved')}
                  className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg font-bold text-sm transition-colors shadow-sm flex items-center gap-2"
                >
                  <CheckCircle className="w-4 h-4" /> Resolve
                </button>
              </div>
            </div>

            {/* Map & Telemetry Grid */}
            <div className="flex-1 overflow-y-auto p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
              
              {/* Interactive Live Map */}
              <div className="lg:col-span-2 rounded-2xl overflow-hidden border border-border shadow-md bg-slate-100 relative min-h-[500px]">
                <LiveIncidentMap 
                  incidents={incidents} 
                  selectedId={selectedIncident.id}
                  onIncidentSelect={setSelectedIncident}
                />
              </div>

              {/* Telemetry Panel */}
              <div className="flex flex-col gap-6">
                
                {/* AI Analysis */}
                <div className="bg-white dark:bg-muted p-5 rounded-2xl border border-border shadow-sm">
                  <h3 className="font-black text-sm uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2">
                    <Activity className="w-4 h-4" /> AI Threat Analysis
                  </h3>
                  <div className="space-y-4">
                    <div>
                      <div className="text-xs text-muted-foreground mb-1">Detected Category</div>
                      <div className="font-bold text-lg capitalize text-red-600 flex items-center gap-2">
                        {selectedIncident.category === 'security' ? <ShieldAlert className="w-5 h-5"/> : <AlertTriangle className="w-5 h-5"/>}
                        {selectedIncident.category}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground mb-1">AI Transcript Summary</div>
                      <p className="text-sm bg-red-50 dark:bg-red-900/10 p-3 rounded-lg border border-red-100 dark:border-red-900/30 font-medium">
                        "User repeatedly mentioned someone trying to snatch their bag. High stress detected in voice."
                      </p>
                    </div>
                  </div>
                </div>

                {/* Device Telemetry */}
                <div className="bg-white dark:bg-muted p-5 rounded-2xl border border-border shadow-sm">
                  <h3 className="font-black text-sm uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2">
                    <Activity className="w-4 h-4" /> Device Telemetry
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-muted/50 p-3 rounded-xl">
                      <div className="text-[10px] uppercase text-muted-foreground font-bold mb-1">Battery</div>
                      <div className={cn("font-black text-lg", selectedIncident.batteryLevel < 30 ? "text-red-600" : "text-green-600")}>
                        {selectedIncident.batteryLevel}%
                      </div>
                    </div>
                    <div className="bg-muted/50 p-3 rounded-xl">
                      <div className="text-[10px] uppercase text-muted-foreground font-bold mb-1">Network</div>
                      <div className="font-black text-sm truncate">
                        {selectedIncident.networkStrength}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Chat Context & Live Admin Chat */}
                <div className="bg-white dark:bg-muted p-5 rounded-2xl border border-border shadow-sm flex-1 flex flex-col min-h-[400px]">
                  <h3 className="font-black text-sm uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2">
                    <MessageCircle className="w-4 h-4" /> Live Secure Chat
                  </h3>
                  
                  {/* Message Feed (Historical + Live) */}
                  <div className="flex-1 overflow-y-auto space-y-3 pr-2 mb-4">
                    {/* Pre-SOS History */}
                    {selectedIncident.chatHistory?.map((msg, i) => (
                      <div key={`hist-${i}`} className={cn(
                        "p-3 rounded-xl text-xs opacity-60",
                        msg.role === 'user' ? "bg-primary/5 border border-primary/10 ml-4" : "bg-muted border border-border mr-4"
                      )}>
                        <div className="font-black uppercase text-[8px] mb-1">{msg.role === 'user' ? selectedIncident.name : 'DIKSHA AI'} • {msg.timestamp}</div>
                        {msg.content}
                      </div>
                    ))}
                    
                    {/* Divider */}
                    <div className="relative py-4">
                        <div className="absolute inset-0 flex items-center"><span className="w-full border-t border-red-200 dark:border-red-900/30" /></div>
                        <div className="relative flex justify-center"><span className="bg-white dark:bg-muted px-2 text-[10px] font-black text-red-600 uppercase tracking-widest">Live Admin Intervention</span></div>
                    </div>

                    {/* Live Admin Chat */}
                    {liveChat.map((msg, i) => (
                      <div key={`live-${i}`} className={cn(
                        "p-3 rounded-xl text-xs animate-in slide-in-from-bottom-2",
                        msg.sender === 'OPS_ADMIN' ? "bg-slate-900 text-white ml-4" : "bg-red-600 text-white mr-4"
                      )}>
                        <div className="font-black uppercase text-[8px] opacity-70 mb-1">{msg.sender} • {new Date(msg.timestamp).toLocaleTimeString()}</div>
                        {msg.content}
                      </div>
                    ))}
                  </div>

                  {/* Input Area */}
                  <div className="relative">
                    <input
                      type="text"
                      value={adminMessage}
                      onChange={(e) => setAdminMessage(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && sendAdminMessage()}
                      placeholder="Type a command or message to passenger..."
                      className="w-full bg-muted border-2 border-border rounded-xl px-4 py-3 pr-12 text-sm outline-none focus:border-primary transition-colors"
                    />
                    <button 
                      onClick={sendAdminMessage}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-primary hover:text-primary/80"
                    >
                      <Send className="w-5 h-5" />
                    </button>
                  </div>
                </div>

                {/* Live Participants HUD */}
                <div className="bg-white dark:bg-muted p-5 rounded-2xl border border-border shadow-sm">
                  <h3 className="font-black text-sm uppercase tracking-wider text-muted-foreground mb-4 flex items-center gap-2">
                    <Users className="w-4 h-4" /> Conference Participants
                  </h3>
                  <div className="flex flex-wrap gap-3">
                    {['Passenger', 'RPF', 'Admin'].map(role => {
                        const isActive = selectedIncident.active_participants?.includes(role);
                        return (
                            <div key={role} className={cn(
                                "flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-bold transition-all",
                                isActive ? "bg-green-50 border-green-200 text-green-700 dark:bg-green-900/20" : "bg-muted border-border text-muted-foreground opacity-50"
                            )}>
                                <div className={cn("w-2 h-2 rounded-full", isActive ? "bg-green-500 animate-pulse" : "bg-muted-foreground")} />
                                {role}
                            </div>
                        )
                    })}
                  </div>
                </div>

                {/* Action Dispatcher */}
                <div className="bg-white dark:bg-muted p-5 rounded-2xl border border-border shadow-sm flex flex-col gap-3">
                  <h3 className="font-black text-sm uppercase tracking-wider text-muted-foreground mb-2 flex items-center gap-2">
                    <Siren className="w-4 h-4" /> Authority Dispatch
                  </h3>
                  
                  {selectedIncident.nearestAuthority ? (
                    <div className="bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-900/30 rounded-xl p-3 mb-2">
                      <div className="text-[10px] font-bold text-green-700 uppercase mb-1">AI Recommendation</div>
                      <div className="font-black text-sm">{selectedIncident.nearestAuthority.name}</div>
                      <div className="text-xs text-muted-foreground">ETA: {selectedIncident.nearestAuthority.eta_mins} mins ({selectedIncident.nearestAuthority.distance_km}km)</div>
                      <button className="w-full mt-3 bg-green-600 text-white hover:bg-green-700 p-2 rounded-lg font-bold text-xs transition-colors flex justify-center items-center gap-2 shadow-sm">
                        <PhoneCall className="w-3 h-3" /> Call {selectedIncident.nearestAuthority.contact_number}
                      </button>
                    </div>
                  ) : (
                    <div className="text-xs text-muted-foreground italic mb-2">No nearby authorities detected automatically.</div>
                  )}
                  
                  <button className="w-full bg-slate-900 text-white hover:bg-slate-800 p-3 rounded-xl font-bold text-sm transition-colors flex justify-center items-center gap-2 shadow-sm">
                    <ShieldAlert className="w-4 h-4" /> Dispatch RPF Manual
                  </button>
                  <button className="w-full bg-red-600 text-white hover:bg-red-700 p-3 rounded-xl font-bold text-sm transition-colors flex justify-center items-center gap-2 shadow-sm">
                    <Activity className="w-4 h-4" /> Dispatch Medical Manual
                  </button>
                  <button className="w-full bg-primary/10 text-primary hover:bg-primary/20 border border-primary/20 p-3 rounded-xl font-bold text-sm transition-colors flex justify-center items-center gap-2 shadow-sm">
                    <MessageCircle className="w-4 h-4" /> Open Secure Chat
                  </button>

                </div>

              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center flex-col text-muted-foreground">
            <ShieldAlert className="w-16 h-16 opacity-20 mb-4" />
            <p className="font-medium">Select an incident from the queue to view telemetry.</p>
          </div>
        )}
      </div>
    </div>
  );
}

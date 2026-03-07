import { useState, useEffect } from "react";
import { Loader2, ClipboardCheck, User, Train, ExternalLink, Upload, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/hooks/use-toast";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export default function AgentPortal() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [claiming, setClaiming] = useState<string | null>(null);
  const [fulfilling, setFulfilling] = useState<string | null>(null);
  
  // Fulfillment Form State
  const [pnr, setPnr] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("auth_token");
      const res = await fetch("http://localhost:8000/api/v2/agent/tasks", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      const data = await res.json();
      setTasks(data);
    } catch (e) {
      toast({ title: "Fetch Failed", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchTasks(); }, []);

  const claimTask = async (id: string) => {
    setClaiming(id);
    try {
      const token = localStorage.getItem("auth_token");
      await fetch(`http://localhost:8000/api/v2/agent/${id}/claim`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` }
      });
      toast({ title: "Task Claimed", description: "You can now fulfill this booking." });
      fetchTasks();
    } catch (e) {
      toast({ title: "Claim Failed", variant: "destructive" });
    } finally {
      setClaiming(null);
    }
  };

  const fulfillTask = async (id: string) => {
    if (!pnr || !file) {
      toast({ title: "Missing Data", description: "Enter PNR and upload the ticket PDF.", variant: "destructive" });
      return;
    }
    setFulfilling(id);
    try {
      const token = localStorage.getItem("auth_token");
      const formData = new FormData();
      formData.append("pnr", pnr);
      formData.append("ticket_file", file);

      const res = await fetch(`http://localhost:8000/api/v2/agent/${id}/fulfill`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` },
        body: formData
      });
      
      if (res.ok) {
        toast({ title: "Booking Fulfilled", description: "The user has been notified." });
        setPnr("");
        setFile(null);
        fetchTasks();
      }
    } catch (e) {
      toast({ title: "Fulfillment Failed", variant: "destructive" });
    } finally {
      setFulfilling(null);
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-8 min-h-screen bg-slate-50/50">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-black tracking-tight flex items-center gap-3">
            <ClipboardCheck className="w-8 h-8 text-primary" />
            Agent Fulfillment Portal
          </h1>
          <p className="text-muted-foreground mt-1 text-sm font-medium">Assisting users with human-touch bookings.</p>
        </div>
        <Button onClick={fetchTasks} variant="outline" className="rounded-xl border-slate-300">
          <RefreshCw className="w-4 h-4 mr-2" /> Refresh Queue
        </Button>
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Loader2 className="w-10 h-10 animate-spin text-primary" /></div>
      ) : tasks.length === 0 ? (
        <Card className="border-dashed py-20 text-center text-muted-foreground">
          <CardContent>No pending verified tasks found.</CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-6">
          {tasks.map((task) => (
            <Card key={task.id} className="overflow-hidden border-border/60 hover:border-primary/40 transition-colors">
              <div className="h-1.5 w-full bg-primary/20" />
              <CardContent className="p-0">
                <div className="p-6 grid md:grid-cols-3 gap-8">
                  {/* Journey Info */}
                  <div className="space-y-3">
                    <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Journey Details</p>
                    <div className="flex items-center gap-3">
                      <div className="bg-primary/10 p-2 rounded-lg text-primary"><Train className="w-5 h-5" /></div>
                      <div>
                        <p className="font-bold text-lg leading-none">{task.booking_details?.train_number || "Train"}</p>
                        <p className="text-xs text-muted-foreground mt-1">{task.booking_details?.boarding_point} → DEST</p>
                      </div>
                    </div>
                    <p className="text-xs font-mono bg-slate-100 p-1.5 rounded inline-block">ID: {task.id}</p>
                  </div>

                  {/* Passenger Info */}
                  <div className="space-y-3">
                    <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Passenger Details</p>
                    <div className="flex items-start gap-3">
                      <div className="bg-slate-100 p-2 rounded-lg text-slate-600"><User className="w-5 h-5" /></div>
                      <div>
                        <p className="font-bold text-sm">{(task.booking_details?.passengers || []).map((p: any) => p.fullName).join(", ")}</p>
                        <p className="text-xs text-muted-foreground mt-1">Status: Verified & Paid</p>
                      </div>
                    </div>
                  </div>

                  {/* Action Area */}
                  <div className="flex flex-col justify-center gap-3">
                    {!task.agent_id ? (
                      <Button 
                        onClick={() => claimTask(task.id)} 
                        disabled={claiming === task.id}
                        className="w-full h-12 rounded-xl font-bold bg-primary hover:bg-primary/90"
                      >
                        {claiming === task.id ? <Loader2 className="w-4 h-4 animate-spin" /> : "Claim this Task"}
                      </Button>
                    ) : (
                      <div className="space-y-4 animate-in fade-in zoom-in duration-300">
                        <div className="flex gap-2">
                          <Input 
                            placeholder="Enter Confirmed PNR" 
                            value={pnr} 
                            onChange={(e) => setPnr(e.target.value)}
                            className="h-12 rounded-xl font-mono text-lg font-bold"
                          />
                          <div className="relative">
                            <input 
                              type="file" 
                              className="hidden" 
                              id={`file-${task.id}`} 
                              onChange={(e) => setFile(e.target.files?.[0] || null)}
                            />
                            <Button asChild variant="outline" className={cn("h-12 w-12 rounded-xl p-0", file && "border-emerald-500 bg-emerald-50")}>
                              <label htmlFor={`file-${task.id}`} className="cursor-pointer">
                                <Upload className={cn("w-5 h-5", file ? "text-emerald-600" : "text-slate-400")} />
                              </label>
                            </Button>
                          </div>
                        </div>
                        <Button 
                          onClick={() => fulfillTask(task.id)} 
                          disabled={fulfilling === task.id}
                          className="w-full h-12 rounded-xl font-bold bg-emerald-600 hover:bg-emerald-700 shadow-lg shadow-emerald-100"
                        >
                          {fulfilling === task.id ? <Loader2 className="w-4 h-4 animate-spin" /> : "Complete Fulfillment"}
                        </Button>
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// Minimal Icons not already imported
function RefreshCw(props: any) {
  return (
    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2} {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
    </svg>
  );
}

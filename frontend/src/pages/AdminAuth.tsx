import { useState } from "react";
import { Shield, Lock, User, Loader2, Zap } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { getApiBase } from "@/lib/apiClient";

export default function AdminAuth() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const res = await fetch(`${getApiBase()}/v2/admin/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });
      
      if (!res.ok) throw new Error("Invalid credentials");
      
      const data = await res.json();
      localStorage.setItem("admin_token", data.access_token);
      toast.success("Access Granted. Initializing Command Center...");
      
      setTimeout(() => {
        navigate("/ops/admin");
      }, 1500);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-black flex items-center justify-center p-4 font-mono">
      {/* Matrix Background Effect (Simulated) */}
      <div className="absolute inset-0 overflow-hidden opacity-20 pointer-events-none">
        <div className="text-green-500 text-[10px] leading-tight whitespace-nowrap animate-pulse">
          {Array(100).fill(0).map(() => Math.random().toString(36).substring(2)).join(" ")}
        </div>
      </div>

      <div className="max-w-md w-full relative z-10">
        <div className="bg-slate-900 border-2 border-green-500/50 shadow-[0_0_30px_rgba(34,197,94,0.2)] rounded-sm p-8 space-y-8">
          <div className="text-center space-y-2">
            <div className="inline-block p-4 bg-green-500/10 rounded-full border border-green-500/20 mb-4">
              <Shield className="w-12 h-12 text-green-500 animate-pulse" />
            </div>
            <h1 className="text-2xl font-black text-white tracking-widest uppercase">Admin Terminal</h1>
            <p className="text-green-500/60 text-xs font-bold uppercase tracking-tighter">Authorized Personnel Only</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-6">
            <div className="space-y-4">
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-green-500/50" />
                <input
                  type="text"
                  placeholder="USERNAME"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full bg-black border border-green-500/30 rounded-none px-10 py-3 text-green-500 placeholder:text-green-900 focus:border-green-500 focus:outline-none transition-colors"
                  required
                />
              </div>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-green-500/50" />
                <input
                  type="password"
                  placeholder="PASSWORD"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-black border border-green-500/30 rounded-none px-10 py-3 text-green-500 placeholder:text-green-900 focus:border-green-500 focus:outline-none transition-colors"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-green-600 hover:bg-green-500 text-black font-black py-4 uppercase tracking-[0.3em] transition-all flex items-center justify-center gap-2 group disabled:opacity-50"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <>
                  Establish Uplink
                  <Zap className="w-4 h-4 fill-current group-hover:scale-125 transition-transform" />
                </>
              )}
            </button>
          </form>

          <div className="pt-4 border-t border-green-500/10 text-center">
            <p className="text-[10px] text-green-900 font-bold uppercase tracking-widest">
              Secured by RouteMaster Cryptography Layer v2.5
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

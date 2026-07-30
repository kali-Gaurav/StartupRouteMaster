import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { ShieldAlert, CheckCircle, Zap, ShieldCheck, HeartHandshake } from "lucide-react";
import { SathiMapOverlay } from "@/components/SathiMapOverlay";

export default function SafetyPage() {
  const safetyFeatures = [
    {
      icon: <ShieldAlert className="w-8 h-8 text-red-500" />,
      title: "One-Tap SOS Trigger",
      description: "Instantly alert railway police, local responders, and your emergency contacts with your precise live GPS coordinates."
    },
    {
      icon: <Zap className="w-8 h-8 text-amber-500" />,
      title: "Proactive Safety Shield",
      description: "Activate real-time journey monitoring for high-risk or late-night travel. Our operations center tracks you every 15 seconds."
    },
    {
      icon: <CheckCircle className="w-8 h-8 text-emerald-500" />,
      title: "Women-Friendly Journey Scoring",
      description: "Our AI evaluates routes based on historical safety data, crowd density, and station lighting to recommend the safest path."
    },
    {
      icon: <ShieldCheck className="w-8 h-8 text-blue-500" />,
      title: "Verified Safe Routes",
      description: "All recommended routes are continuously verified through real-time telemetry from thousands of active journeys."
    },
    {
      icon: <HeartHandshake className="w-8 h-8 text-indigo-500" />,
      title: "Sathi Safety Companions",
      description: "Verified personnel available at major stations to assist women and family travelers. Look for the Sathi icon on the map."
    }
  ];

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar />
      <main className="flex-1 container mx-auto px-4 py-24 max-w-4xl text-center">
        <h1 className="text-5xl font-black uppercase tracking-tighter mb-6 italic italic text-gradient">
          Safety First Architecture
        </h1>
        <p className="text-xl text-muted-foreground mb-16 max-w-2xl mx-auto">
          At RouteMaster, we believe that travel should be as safe as it is convenient. Our platform is built on a "Safety First" foundation.
        </p>

        <div className="grid md:grid-cols-2 gap-8 text-left">
          {safetyFeatures.map((f, i) => (
            <div key={i} className="p-8 bg-card border-2 border-border rounded-3xl hover:border-primary/50 transition-all group">
              <div className="mb-6 p-4 bg-muted rounded-2xl w-fit group-hover:bg-primary/10 transition-colors">
                {f.icon}
              </div>
              <h3 className="text-2xl font-bold mb-3">{f.title}</h3>
              <p className="text-muted-foreground leading-relaxed">{f.description}</p>
            </div>
          ))}
        </div>

        {/* Real-time Sathi Map Section */}
        <div className="mt-24 text-left">
           <div className="flex items-center gap-4 mb-8">
              <div className="p-3 bg-emerald-100 rounded-2xl">
                 <ShieldCheck className="w-8 h-8 text-emerald-600" />
              </div>
              <div>
                 <h2 className="text-3xl font-black uppercase tracking-tighter italic">Sathi Near Me</h2>
                 <p className="text-muted-foreground">Real-time distribution of verified safety personnel in your vicinity.</p>
              </div>
           </div>
           
           <div className="h-[500px] w-full rounded-[2.5rem] overflow-hidden border-4 border-white shadow-2xl relative">
              <SathiMapOverlay className="w-full h-full" />
           </div>
           
           <div className="mt-8 p-8 bg-emerald-600 text-white rounded-3xl flex flex-col md:flex-row items-center justify-between gap-6 shadow-xl animate-in zoom-in duration-500">
              <div className="flex items-center gap-4">
                 <div className="p-3 bg-white/20 rounded-2xl">
                    <HeartHandshake className="w-8 h-8" />
                 </div>
                 <div>
                    <h3 className="text-xl font-bold italic tracking-tighter uppercase">Become a Sathi</h3>
                    <p className="text-emerald-100 text-sm">Join our mission to make railway travel safe for everyone.</p>
                 </div>
              </div>
              <a 
                href="/sathi/onboard" 
                className="px-8 py-4 bg-white text-emerald-700 rounded-2xl font-black uppercase tracking-widest hover:scale-105 active:scale-95 transition-all shadow-lg"
              >
                Apply Now
              </a>
           </div>
           
           <div className="mt-6 flex flex-wrap gap-4 justify-center md:justify-start">
              <div className="flex items-center gap-2 px-4 py-2 bg-emerald-50 text-emerald-700 rounded-full text-xs font-bold border border-emerald-100">
                 <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                 Verified & Active
              </div>
              <div className="flex items-center gap-2 px-4 py-2 bg-blue-50 text-blue-700 rounded-full text-xs font-bold border border-blue-100">
                 GPS Tracked
              </div>
              <div className="flex items-center gap-2 px-4 py-2 bg-amber-50 text-amber-700 rounded-full text-xs font-bold border border-amber-100">
                 Background Checked
              </div>
           </div>
        </div>

        <div className="mt-20 p-12 bg-slate-900 text-white rounded-[2.5rem] relative overflow-hidden text-left shadow-2xl">
          <div className="absolute top-0 right-0 p-8 opacity-20">
             <ShieldAlert className="w-48 h-48" />
          </div>
          <h2 className="text-4xl font-black uppercase tracking-tighter italic mb-6">Our Operations Center</h2>
          <p className="text-slate-400 text-lg leading-relaxed max-w-xl mb-8">
            Your safety is backed by a 24/7 active monitoring center that analyzes telemetry data in real-time. We're not just an app; we're your companion on the tracks.
          </p>
          <div className="flex gap-4">
             <div className="px-4 py-2 bg-red-600 rounded-lg text-sm font-bold uppercase tracking-widest">Live 24/7</div>
             <div className="px-4 py-2 bg-blue-600 rounded-lg text-sm font-bold uppercase tracking-widest">AI Assisted</div>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}

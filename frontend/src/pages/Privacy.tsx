import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { Shield } from "lucide-react";

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar />
      <main className="flex-1 container mx-auto px-4 py-24 max-w-4xl">
        <div className="flex items-center gap-3 mb-8">
          <div className="p-3 bg-emerald-500/10 rounded-2xl">
            <Shield className="w-8 h-8 text-emerald-500" />
          </div>
          <h1 className="text-4xl font-bold tracking-tight">Privacy Policy</h1>
        </div>
        
        <div className="prose prose-slate dark:prose-invert max-w-none space-y-8">
          <section>
            <h2 className="text-2xl font-bold mb-4">1. Data Collection</h2>
            <p className="text-muted-foreground leading-relaxed">
              At RouteMaster, we collect essential data to ensure your safety and provide optimal routing. This includes your phone number for authentication, and real-time location data when you activate SOS or Safety Shield features.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-bold mb-4">2. Location Tracking</h2>
            <p className="text-muted-foreground leading-relaxed">
              Location tracking is only active when specifically requested by you through our safety features. This data is transmitted securely to our operations center and, in the event of an SOS trigger, to authorized railway police and emergency responders.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-bold mb-4">3. Data Security</h2>
            <p className="text-muted-foreground leading-relaxed">
              We employ industry-standard encryption and security protocols to protect your personal information. Your data is stored on secure servers and is never sold to third parties.
            </p>
          </section>

          <div className="p-6 bg-muted rounded-2xl border border-border mt-12">
            <p className="text-sm font-medium italic">
              Last Updated: February 2026. This is a placeholder policy for development purposes.
            </p>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}

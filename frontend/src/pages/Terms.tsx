import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { FileText } from "lucide-react";

export default function TermsPage() {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navbar />
      <main className="flex-1 container mx-auto px-4 py-24 max-w-4xl">
        <div className="flex items-center gap-3 mb-8">
          <div className="p-3 bg-blue-500/10 rounded-2xl">
            <FileText className="w-8 h-8 text-blue-500" />
          </div>
          <h1 className="text-4xl font-bold tracking-tight">Terms of Service</h1>
        </div>
        
        <div className="prose prose-slate dark:prose-invert max-w-none space-y-8">
          <section>
            <h2 className="text-2xl font-bold mb-4">1. Acceptance of Terms</h2>
            <p className="text-muted-foreground leading-relaxed">
              By using RouteMaster, you agree to these terms and conditions. If you do not agree to these terms, please do not use our application.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-bold mb-4">2. Safety and SOS Features</h2>
            <p className="text-muted-foreground leading-relaxed">
              RouteMaster's safety features are designed to provide assistance during travel. While we strive for 100% uptime and accuracy, our service depends on external factors like network availability and GPS satellite signals. 
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-bold mb-4">3. User Responsibility</h2>
            <p className="text-muted-foreground leading-relaxed">
              Users are responsible for maintaining the confidentiality of their account information and for all activities that occur under their account. 
            </p>
          </section>

          <div className="p-6 bg-muted rounded-2xl border border-border mt-12">
            <p className="text-sm font-medium italic">
              Last Updated: February 2026. This is a placeholder terms document for development purposes.
            </p>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}

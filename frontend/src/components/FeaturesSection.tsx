import { Train, Zap, Shield, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

const features = [
  {
    icon: Zap,
    title: "Pareto-Optimal Routes",
    description: "AI finds mathematically optimal routes balancing time, cost, and comfort.",
    gradient: "from-amber-500 to-orange-500",
  },
  {
    icon: Train,
    title: "Multi-Transfer Support",
    description: "Seamlessly connects multiple trains to reach any destination.",
    gradient: "from-blue-500 to-cyan-500",
  },
  {
    icon: Shield,
    title: "Seat Probability",
    description: "Know your chances of getting confirmed seats before booking.",
    gradient: "from-green-500 to-emerald-500",
  },
  {
    icon: Clock,
    title: "Real-time Updates",
    description: "Live train status, delays, and platform changes.",
    gradient: "from-purple-500 to-violet-500",
  },
];

export function FeaturesSection() {
  return (
    <section className="py-20">
      <div className="container mx-auto px-4">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
            Why Choose <span className="text-gradient">ParetoRoute</span>?
          </h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            Our AI-powered optimizer analyzes thousands of routes to find the perfect balance for your journey.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map((feature, idx) => (
            <div
              key={feature.title}
              className={cn(
                "group p-6 rounded-2xl bg-card border border-border",
                "hover:border-primary/30 hover:shadow-card transition-all duration-300",
                "animate-slide-in opacity-0"
              )}
              style={{ animationDelay: `${idx * 0.1}s`, animationFillMode: "forwards" }}
            >
              <div
                className={cn(
                  "w-12 h-12 rounded-xl flex items-center justify-center mb-4",
                  "bg-gradient-to-br",
                  feature.gradient,
                  "group-hover:scale-110 transition-transform duration-300"
                )}
              >
                <feature.icon className="w-6 h-6 text-white" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">
                {feature.title}
              </h3>
              <p className="text-sm text-muted-foreground">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

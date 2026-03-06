import { Check, Loader2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export interface Step {
  id: string;
  label: string;
  description: string;
}

interface StepperProps {
  steps: Step[];
  currentStepIndex: number;
  isFailed?: boolean;
}

export function Stepper({ steps, currentStepIndex, isFailed }: StepperProps) {
  return (
    <div className="flex flex-col gap-6 relative">
      {/* Connecting line */}
      <div className="absolute left-[19px] top-4 bottom-4 w-0.5 bg-border/60 z-0 rounded-full" />
      
      {/* Active line fill */}
      <div 
        className="absolute left-[19px] top-4 w-0.5 bg-primary z-0 rounded-full transition-all duration-700 ease-in-out" 
        style={{ 
          height: isFailed 
            ? `${(currentStepIndex / (steps.length - 1)) * 100}%` 
            : `${(Math.max(0, currentStepIndex - 0.5) / (steps.length - 1)) * 100}%`,
          backgroundColor: isFailed ? 'hsl(var(--destructive))' : 'hsl(var(--primary))'
        }} 
      />

      {steps.map((step, index) => {
        const isCompleted = index < currentStepIndex;
        const isCurrent = index === currentStepIndex;
        const isPending = index > currentStepIndex;
        
        // Status colors and icons
        let icon = <div className="w-2.5 h-2.5 rounded-full bg-muted-foreground" />;
        let circleClass = "bg-background border-2 border-muted";
        
        if (isCompleted) {
          icon = <Check className="w-5 h-5 text-white" />;
          circleClass = "bg-primary border-primary shadow-md";
        } else if (isCurrent) {
          if (isFailed) {
            icon = <XCircle className="w-6 h-6 text-destructive" />;
            circleClass = "bg-background border-2 border-destructive text-destructive bg-destructive/10";
          } else {
            icon = <Loader2 className="w-5 h-5 text-primary animate-spin" />;
            circleClass = "bg-background border-2 border-primary animate-pulse-ring";
          }
        }

        return (
          <div key={step.id} className="flex gap-4 relative z-10">
            <div className="flex flex-col items-center">
              <div className={cn(
                "w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300 z-10",
                circleClass
              )}>
                {icon}
              </div>
            </div>
            
            <div className={cn(
              "flex flex-col pt-1.5 pb-4 transition-opacity duration-300",
              isPending ? "opacity-50" : "opacity-100"
            )}>
              <h4 className={cn(
                "font-semibold text-base",
                isCurrent && !isFailed ? "text-primary" : 
                isCurrent && isFailed ? "text-destructive" : 
                isCompleted ? "text-foreground" : "text-muted-foreground"
              )}>
                {step.label}
              </h4>
              <p className="text-sm text-muted-foreground mt-0.5">
                {step.description}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

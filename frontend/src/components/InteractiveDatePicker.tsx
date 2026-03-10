import { useState } from "react";
import { format, addDays } from "date-fns";
import { Calendar as CalendarIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface InteractiveDatePickerProps {
  onDateSelect: (date: string) => void;
  minDate?: Date;
}

export function InteractiveDatePicker({ onDateSelect, minDate = new Date() }: InteractiveDatePickerProps) {
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  
  // Quick options
  const options = [
    { label: "Today", date: new Date() },
    { label: "Tomorrow", date: addDays(new Date(), 1) },
    { label: "Day After", date: addDays(new Date(), 2) },
  ];

  return (
    <div className="bg-white dark:bg-muted border border-border rounded-2xl p-4 shadow-sm space-y-4 w-full max-w-[280px]">
      <div className="flex items-center gap-2 text-primary font-bold text-sm mb-2">
        <CalendarIcon className="w-4 h-4" />
        Select Journey Date
      </div>
      
      <div className="grid grid-cols-1 gap-2">
        {options.map((opt) => (
          <button
            key={opt.label}
            onClick={() => {
              const d = format(opt.date, "yyyy-MM-dd");
              onDateSelect(d);
            }}
            className="flex justify-between items-center px-4 py-2.5 rounded-xl bg-primary/5 hover:bg-primary/10 text-sm font-medium transition-colors border border-primary/10"
          >
            <span>{opt.label}</span>
            <span className="text-xs opacity-60">{format(opt.date, "EEE, dd MMM")}</span>
          </button>
        ))}
      </div>
      
      <div className="pt-2 border-t border-border mt-2">
        <label className="text-[10px] uppercase font-black text-muted-foreground tracking-wider mb-2 block">
          Custom Date
        </label>
        <input
          type="date"
          min={format(minDate, "yyyy-MM-dd")}
          onChange={(e) => onDateSelect(e.target.value)}
          className="w-full bg-background border-2 border-border rounded-xl px-3 py-2 text-sm outline-none focus:border-primary transition-colors"
        />
      </div>
    </div>
  );
}

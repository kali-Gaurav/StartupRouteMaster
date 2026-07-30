import { useState, useEffect, useCallback } from "react";
import { Mic, MicOff, Search, Sparkles, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "@/hooks/use-toast";
import { getRailwayApiUrl } from "@/lib/utils";

interface VoiceSearchProps {
  onSearchResolved: (source: string, destination: string, date: string) => void;
  className?: string;
}

export const VoiceSearch = ({ onSearchResolved, className }: VoiceSearchProps) => {
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [recognition, setRecognition] = useState<any>(null);

  useEffect(() => {
    // Initialize Web Speech API
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      const rec = new SpeechRecognition();
      rec.continuous = false;
      rec.interimResults = true;
      rec.lang = "en-IN"; // Target Indian English for better station name detection

      rec.onstart = () => {
        setIsListening(true);
        setTranscript("");
      };

      rec.onresult = (event: any) => {
        const current = event.resultIndex;
        const result = event.results[current][0].transcript;
        setTranscript(result);
      };

      rec.onerror = (event: any) => {
        console.error("Speech recognition error", event.error);
        setIsListening(false);
        if (event.error === "aborted") {
          return;
        }
        toast({
          title: "Voice Error",
          description: `Failed to hear you: ${event.error}`,
          variant: "destructive",
        });
      };

      rec.onend = () => {
        setIsListening(false);
      };

      setRecognition(rec);
    }
  }, []);

  const toggleListening = useCallback(() => {
    if (isListening) {
      recognition?.stop();
    } else {
      if (!recognition) {
        toast({
          title: "Not Supported",
          description: "Your browser doesn't support voice search.",
          variant: "destructive",
        });
        return;
      }
      recognition.start();
    }
  }, [isListening, recognition]);

  useEffect(() => {
    if (!isListening && transcript.length > 5 && !isProcessing) {
      handleParseVoiceQuery(transcript);
    }
  }, [isListening, transcript]);

  const handleParseVoiceQuery = async (query: string) => {
    setIsProcessing(true);
    try {
      const res = await fetch(getRailwayApiUrl(`/v1/voice/parse?q=${encodeURIComponent(query)}`));
      if (!res.ok) throw new Error("Voice parse failed");
      
      const data = await res.json();
      if (data.action === "EXECUTE_SEARCH") {
        const { source, destination, date } = data.params;
        
        // Convert temporal dates
        let actualDate = new Date().toISOString().slice(0, 10);
        if (date === "tomorrow") {
          const tomorrow = new Date();
          tomorrow.setDate(tomorrow.getDate() + 1);
          actualDate = tomorrow.toISOString().slice(0, 10);
        }

        onSearchResolved(source, destination, actualDate);
        toast({
          title: "Voice Intent Detected",
          description: data.speech_response,
          className: "bg-blue-600 text-white",
        });
      } else {
        toast({
          title: "Clarification Needed",
          description: data.speech_response,
        });
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className={cn("relative flex items-center gap-2", className)}>
      <button
        onClick={toggleListening}
        disabled={isProcessing}
        className={cn(
          "w-12 h-12 rounded-full flex items-center justify-center transition-all shadow-lg",
          isListening 
            ? "bg-red-500 text-white animate-pulse scale-110 shadow-red-500/40" 
            : "bg-primary text-primary-foreground hover:scale-105 active:scale-95 shadow-primary/20",
          isProcessing && "opacity-50 cursor-not-allowed"
        )}
      >
        {isProcessing ? (
          <Loader2 className="w-5 h-5 animate-spin" />
        ) : isListening ? (
          <Mic className="w-5 h-5" />
        ) : (
          <Mic className="w-5 h-5" />
        )}
      </button>

      {isListening && (
        <div className="absolute left-14 whitespace-nowrap px-4 py-2 rounded-xl bg-card border border-border shadow-md animate-in fade-in slide-in-from-left-2">
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-bounce [animation-delay:-0.3s]" />
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-bounce [animation-delay:-0.15s]" />
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-bounce" />
            </div>
            <p className="text-xs font-medium italic opacity-70">
              {transcript || "Listening..."}
            </p>
          </div>
        </div>
      )}
      
      {!isListening && transcript && !isProcessing && (
         <div className="absolute left-14 whitespace-nowrap px-4 py-2 rounded-xl bg-blue-600 text-white shadow-md animate-in fade-in slide-in-from-left-2">
            <p className="text-xs font-bold flex items-center gap-2">
              <Sparkles className="w-3 h-3" /> {transcript}
            </p>
         </div>
      )}
    </div>
  );
};

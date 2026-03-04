import { useState, useEffect, useCallback } from "react";

export function useSOSWakeWord(onTrigger: () => void) {
  const [isListening, setIsListening] = useState(false);

  const startListening = useCallback(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
      console.warn("Speech Recognition not supported in this browser.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-IN'; // Support Indian English

    recognition.onstart = () => setIsListening(true);
    recognition.onend = () => {
      setIsListening(false);
      // Auto-restart if needed (careful with battery)
    };

    recognition.onresult = (event: any) => {
      const transcript = Array.from(event.results)
        .map((result: any) => result[0])
        .map((result: any) => result.transcript)
        .join('')
        .toLowerCase();

      const wakeWords = ["help help", "save me", "emergency", "diksha help"];
      
      if (wakeWords.some(word => transcript.includes(word))) {
        console.log("WAKE WORD DETECTED:", transcript);
        onTrigger();
        recognition.stop();
      }
    };

    recognition.start();
  }, [onTrigger]);

  return { isListening, startListening };
}

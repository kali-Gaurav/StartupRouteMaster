/**
 * Diksha Wake-Word System - Hands-free activation.
 */

export function listenWakeWord(onWake: () => void) {
  const SpeechRecognition =
    (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

  if (!SpeechRecognition) return;

  const recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = false;
  recognition.lang = "en-US";

  recognition.onresult = (event: any) => {
    const text = event.results[event.results.length - 1][0].transcript.toLowerCase();
    
    // Check for "Hey Diksha" or similar phonetics
    if (text.includes("hey diksha") || text.includes("diksha") || text.includes("hi diksha")) {
      onWake();
    }
  };

  // Restart on end to keep listening
  recognition.onend = () => {
    try {
      recognition.start();
    } catch (e) {
      // already started or blocked
    }
  };

  try {
    recognition.start();
  } catch (e) {
    console.warn("Wake-word listener failed to start:", e);
  }

  return () => {
    recognition.onend = null;
    recognition.stop();
  };
}

import React, { createContext, useContext, useState, ReactNode } from 'react';
import hi from '../i18n/locales/hi.json';

type Language = 'en' | 'hi' | 'bn';

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string) => string;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

const translations: any = {
  hi: hi,
  en: {
    sos: {
      title: "Emergency SOS",
      stealth_mode: "Stealth Mode",
      voice_trigger: "Voice Trigger",
      triggered: "SOS Triggered",
      dispatching: "Encrypting Signal...",
      help_on_way: "Help is on the way",
      sathi_nearby: "4 Verified Sathis nearby have accepted your signal.",
      cancel: "CANCEL (I AM SAFE)",
      secure_now: "I AM SECURE NOW"
    },
    sathi: {
      onboard_title: "Join the Sathi Network",
      kyc_verification: "Identity Verification",
      go_online: "Go Online",
      go_offline: "Go Offline",
      active_online: "Active & Online",
      trust_score: "Trust Score"
    },
    common: {
      next: "Next",
      back: "Back",
      submit: "Submit",
      loading: "Loading..."
    }
  }
};

export const LanguageProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [language, setLanguage] = useState<Language>('en');

  const t = (path: string): string => {
    const keys = path.split('.');
    let current = translations[language];
    for (const key of keys) {
      if (current[key]) {
        current = current[key];
      } else {
        return path; // Fallback to key name
      }
    }
    return typeof current === 'string' ? current : path;
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useTranslation = () => {
  const context = useContext(LanguageContext);
  if (context === undefined) {
    throw new Error('useTranslation must be used within a LanguageProvider');
  }
  return context;
};

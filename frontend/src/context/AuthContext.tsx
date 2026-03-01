/**
 * Authentication Context
 * Manages user authentication state using Supabase
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { supabase } from '@/lib/supabase';
import { Session, User as SupabaseUser } from '@supabase/supabase-js';
import { configureApiClient } from '@/lib/apiClient';

export interface User {
  user_id: string | number;
  phone?: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  profile_photo_url?: string;
  created_at?: string;
  role?: string;
  location_enabled?: boolean; // Added for production telemetry
  // legacy compatibility
  telegram_id?: number;
}

interface AuthContextType {
  user: User | null;
  supabaseUser: SupabaseUser | null;
  session: Session | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (newToken: string, newUser: User, refreshToken?: string) => void;
  logout: () => Promise<void>;
  updateUser: (user: User) => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let sub: any = null;

    // 1. Get initial session
    supabase.auth.getSession().then(({ data: { session: initialSession } }) => {
      setSession(initialSession);
      if (initialSession?.user) {
        setUser(mapSupabaseUser(initialSession.user));
      }
      setIsLoading(false);
    });

    // 2. Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
      setUser(newSession?.user ? mapSupabaseUser(newSession.user) : null);
      setIsLoading(false);
    });
    sub = subscription;

    // 3. Configure API client for global error handling
    configureApiClient({
      on401: () => logout(),
    });

    return () => {
      if (sub) sub.unsubscribe();
    };
  }, []);

  const mapSupabaseUser = (u: SupabaseUser): User => ({
    user_id: u.id,
    email: u.email,
    phone: u.phone,
    first_name: u.user_metadata?.first_name || u.user_metadata?.full_name?.split(' ')[0],
    last_name: u.user_metadata?.last_name || u.user_metadata?.full_name?.split(' ').slice(1).join(' '),
    profile_photo_url: u.user_metadata?.avatar_url,
    role: u.user_metadata?.role || 'user',
    created_at: u.created_at,
    telegram_id: u.user_metadata?.telegram_id
  });

  const logout = async () => {
    await supabase.auth.signOut();
  };

  const login = (newToken: string, newUser: User, refreshToken?: string) => {
    // legacy login placeholder
    console.warn("Legacy login() called. Auth is now handled by Supabase.");
    setUser(newUser);
    // Persist tokens for legacy services if needed
    if (newToken) localStorage.setItem('supabase.auth.token', newToken);
    if (refreshToken) localStorage.setItem('supabase.auth.refreshToken', refreshToken);
  };

  const updateUser = (newUser: User) => {
    setUser(newUser);
  };

  const refreshUser = async () => {
    const { data: { user: u } } = await supabase.auth.getUser();
    if (u) setUser(mapSupabaseUser(u));
  };

  const value = {
    user,
    supabaseUser: session?.user ?? null,
    session,
    token: session?.access_token ?? null,
    isAuthenticated: !!session?.user,
    isLoading,
    login,
    logout,
    updateUser,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

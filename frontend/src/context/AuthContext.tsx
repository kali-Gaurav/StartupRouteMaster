import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { auth } from '@/lib/firebase';
import { onAuthStateChanged, User as FirebaseUser, signOut } from 'firebase/auth';
import { configureApiClient } from '@/lib/apiClient';
import { getRailwayApiUrl } from '@/lib/utils';

export interface User {
  user_id: string;
  id?: string;
  phone?: string | null;
  email?: string | null;
  first_name?: string;
  last_name?: string;
  full_name?: string;
  profile_photo_url?: string | null;
  created_at?: string;
  role?: string;
  isVerified?: boolean;
}

interface AuthContextType {
  user: User | null;
  firebaseUser: FirebaseUser | null;
  /** Backend JWT token — use this for API calls that require auth */
  token: string | null;
  /** Firebase ID token — valid Firebase credential */
  firebaseToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  logout: () => Promise<void>;
  updateUser: (user: User) => void;
  refreshUser: () => Promise<void>;
  /** Legacy compat — some pages read session?.access_token */
  session: { access_token: string | null } | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

/**
 * Sync Firebase user with our backend.
 * Exchanges Firebase profile data for a backend JWT.
 * Non-blocking — search works even if this fails.
 */
async function syncWithBackend(fbUser: FirebaseUser): Promise<string | null> {
  try {
    const res = await fetch(getRailwayApiUrl('/api/v1/auth/firebase-sync'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        firebase_uid: fbUser.uid,
        email: fbUser.email,
        display_name: fbUser.displayName || '',
        photo_url: fbUser.photoURL || '',
      }),
      signal: AbortSignal.timeout(5000),
    });
    if (res.ok) {
      const data = await res.json();
      return data.access_token || null;
    }
  } catch {
    // Backend sync is optional — don't block login
  }
  return null;
}

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [firebaseUser, setFirebaseUser] = useState<FirebaseUser | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [firebaseToken, setFirebaseToken] = useState<string | null>(null);
  const [backendToken, setBackendToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (fbUser) => {
      setFirebaseUser(fbUser);
      if (fbUser) {
        const idToken = await fbUser.getIdToken();
        setFirebaseToken(idToken);
        setUser(mapFirebaseUser(fbUser));
        // Sync with backend (non-blocking) to get backend JWT
        syncWithBackend(fbUser).then(bt => {
          if (bt) setBackendToken(bt);
        });
      } else {
        setFirebaseToken(null);
        setBackendToken(null);
        setUser(null);
      }
      setIsLoading(false);
    });

    configureApiClient({ on401: () => logout() });
    return () => unsubscribe();
  }, []);

  const mapFirebaseUser = (u: FirebaseUser): User => {
    const names = u.displayName?.split(' ') || [];
    return {
      user_id: u.uid,
      id: u.uid,
      email: u.email,
      phone: u.phoneNumber,
      first_name: names[0] || '',
      last_name: names.slice(1).join(' ') || '',
      full_name: u.displayName || '',
      profile_photo_url: u.photoURL,
      role: 'user',
      isVerified: u.emailVerified,
      created_at: u.metadata.creationTime,
    };
  };

  const logout = async () => {
    await signOut(auth);
    setBackendToken(null);
  };

  const updateUser = (newUser: User) => setUser(newUser);

  const refreshUser = async () => {
    if (auth.currentUser) {
      const idToken = await auth.currentUser.getIdToken(true);
      setFirebaseToken(idToken);
      setUser(mapFirebaseUser(auth.currentUser));
    }
  };

  // Prefer backend token for API calls, fall back to Firebase token
  const token = backendToken || firebaseToken;

  const value: AuthContextType = {
    user,
    firebaseUser,
    token,
    firebaseToken,
    isAuthenticated: !!firebaseUser,
    isLoading,
    logout,
    updateUser,
    refreshUser,
    // Legacy compat
    session: token ? { access_token: token } : null,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

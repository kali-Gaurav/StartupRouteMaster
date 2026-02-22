/**
 * Authentication Context
 * Manages user authentication state and JWT tokens
 */

import React, { createContext, useContext, useState, useEffect, useRef, ReactNode } from 'react';
import { configureApiClient } from '@/lib/apiClient';

export interface User {
  user_id: number;
  phone?: string;
  email?: string;
  google_id?: string;
  telegram_id?: number;
  first_name?: string;
  last_name?: string;
  profile_photo_url?: string;
  preferred_class?: string;
  preferred_language?: string;
  notifications_enabled?: boolean;
  location_enabled?: boolean;
  is_verified?: boolean;
  created_at?: string;
  last_login_at?: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (token: string, user: User, refreshToken?: string) => void;
  logout: () => void;
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

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const logoutRef = useRef<() => void>(() => {});

  // Load auth state from localStorage on mount
  useEffect(() => {
    const loadAuthState = () => {
      try {
        const storedToken = localStorage.getItem('auth_token');
        const storedUser = localStorage.getItem('auth_user');
        const storedRefresh = localStorage.getItem('refresh_token');

        if (storedToken && storedUser) {
          setToken(storedToken);
          setUser(JSON.parse(storedUser));
        }
        if (storedRefresh) {
          setRefreshToken(storedRefresh);
        }
      } catch (error) {
        console.error('Failed to load auth state:', error);
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_user');
        localStorage.removeItem('refresh_token');
      } finally {
        setIsLoading(false);
      }
    };

    loadAuthState();
  }, []);

  const login = (newToken: string, newUser: User, newRefreshToken?: string) => {
    setToken(newToken);
    setUser(newUser);
    localStorage.setItem('auth_token', newToken);
    localStorage.setItem('auth_user', JSON.stringify(newUser));
    if (newRefreshToken) {
      setRefreshToken(newRefreshToken);
      localStorage.setItem('refresh_token', newRefreshToken);
    }
  };

  const logout = async () => {
    try {
      // Call logout API (include refresh token so backend can revoke it)
      if (token) {
        await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/auth/logout`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      }
    } catch (error) {
      console.error('Logout API error:', error);
    } finally {
      // Clear local state
      setToken(null);
      setRefreshToken(null);
      setUser(null);
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
      localStorage.removeItem('refresh_token');
    }
  };

  const updateUser = (newUser: User) => {
    setUser(newUser);
    localStorage.setItem('auth_user', JSON.stringify(newUser));
  };

  const refreshUser = async () => {
    if (!token) return;
    try {
      const { getCurrentUser } = await import('@/lib/authApi');
      const user = await getCurrentUser();
      if (user) updateUser(user);
    } catch (error) {
      console.error('Failed to refresh user:', error);
    }
  };

  logoutRef.current = logout;
  useEffect(() => {
    configureApiClient({
      getToken: () => token,
      on401: () => logoutRef.current(),
      onTokenRefresh: (newTok, newRefresh) => {
        setToken(newTok);
        localStorage.setItem('auth_token', newTok);
        if (newRefresh) {
          setRefreshToken(newRefresh);
          localStorage.setItem('refresh_token', newRefresh);
        }
      },
    });
  }, [token]);

  const value: AuthContextType = {
    user,
    token,
    isAuthenticated: !!token && !!user,
    isLoading,
    login,
    logout,
    updateUser,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

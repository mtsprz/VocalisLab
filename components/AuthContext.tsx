import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface User {
  id: string;
  email: string;
  name: string;
  picture: string;
  access_token: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check localStorage for existing session
    const saved = localStorage.getItem('vocalislab_user');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (parsed.id && parsed.access_token) {
          setUser(parsed);
        }
      } catch {}
    }
    setLoading(false);
  }, []);

  const login = async () => {
    try {
      const r = await fetch(`${BACKEND_URL}/api/auth/google/url`);
      const data = await r.json();
      if (data.url) {
        window.location.href = data.url;
      }
    } catch (e) {
      console.error('Error getting Google auth URL:', e);
    }
  };

  const logout = () => {
    localStorage.removeItem('vocalislab_user');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { CLAVE_USUARIO, EVENTO_SESION_VENCIDA } from '../utils/authFetch';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface User {
  id: string;
  email: string;
  name: string;
  picture: string;
  access_token: string;
  /** Token de sesión firmado por el servidor (va en cada pedido). */
  session_token: string;
}

const MENSAJES_ERROR: Record<string, string> = {
  no_autorizado: 'Esta cuenta de Google no está autorizada para usar la plataforma.',
  sin_configurar: 'El servidor todavía no tiene cuentas autorizadas (variable EMAILS_PERMITIDOS en Render).',
  sesion_vencida: 'Tu sesión venció. Volvé a iniciar sesión.',
};

interface AuthContextType {
  user: User | null;
  loading: boolean;
  /** Motivo por el que no se pudo entrar (se muestra en el login). */
  authError: string;
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
  const [authError, setAuthError] = useState('');

  useEffect(() => {
    // Sesión vencida o cuenta quitada: el servidor respondió 401.
    const alVencer = () => {
      setUser(null);
      setAuthError(MENSAJES_ERROR.sesion_vencida);
    };
    window.addEventListener(EVENTO_SESION_VENCIDA, alVencer);

    const params = new URLSearchParams(window.location.search);
    const error = params.get('auth_error');
    if (error) {
      setAuthError(MENSAJES_ERROR[error] || 'No se pudo iniciar sesión.');
      window.history.replaceState({}, '', window.location.pathname);
    }
    // Vuelta del login de Google con los datos del usuario y su sesión.
    if (params.get('auth') === '1' && params.get('user')) {
      try {
        const decoded = JSON.parse(atob(params.get('user')!));
        if (decoded.session_token) {
          localStorage.setItem(CLAVE_USUARIO, JSON.stringify(decoded));
          setUser(decoded);
        }
        window.history.replaceState({}, '', window.location.pathname);
      } catch {}
      setLoading(false);
      return () => window.removeEventListener(EVENTO_SESION_VENCIDA, alVencer);
    }
    // Sesión guardada: sin token de sesión (versión vieja) hay que volver a
    // entrar, porque el servidor ya no acepta pedidos sin sesión.
    const saved = localStorage.getItem(CLAVE_USUARIO);
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (parsed.id && parsed.session_token) {
          setUser(parsed);
        } else {
          localStorage.removeItem(CLAVE_USUARIO);
        }
      } catch {}
    }
    setLoading(false);
    return () => window.removeEventListener(EVENTO_SESION_VENCIDA, alVencer);
  }, []);

  const login = async () => {
    setAuthError('');
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
    localStorage.removeItem(CLAVE_USUARIO);
    try {
      // PWA: la lista mínima offline se borra al cerrar sesión (sin diagnósticos igual)
      localStorage.removeItem('vocalislab_pacientes_min');
    } catch {}
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, authError, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
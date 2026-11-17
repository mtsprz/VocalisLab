/**
 * Agrega el token de sesión a cada pedido al servidor de la app.
 *
 * El servidor exige sesión en /api/* (login obligatorio: son datos de
 * salud). En lugar de tocar cada fetch de la app, se envuelve window.fetch
 * una sola vez: los pedidos al backend salen con
 * `Authorization: Bearer <session_token>`. Si el servidor responde 401
 * (sesión vencida o cuenta quitada de la lista), se borra la sesión local y
 * se avisa a AuthContext para volver a la pantalla de login.
 */
const BACKEND_URL: string = (import.meta as any).env?.VITE_BACKEND_URL || '';
export const CLAVE_USUARIO = 'vocalislab_user';
export const EVENTO_SESION_VENCIDA = 'vocalislab:sesion-vencida';

export function tokenSesion(): string {
  try {
    const u = JSON.parse(localStorage.getItem(CLAVE_USUARIO) || 'null');
    return (u && typeof u.session_token === 'string') ? u.session_token : '';
  } catch {
    return '';
  }
}

function urlDe(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input;
  if (input instanceof URL) return input.href;
  return (input as Request).url;
}

function esDelServidor(url: string): boolean {
  if (url.startsWith('/api/')) return true;
  return Boolean(BACKEND_URL) && url.startsWith(`${BACKEND_URL.replace(/\/$/, '')}/api/`);
}

let instalado = false;

export function instalarAuthFetch(): void {
  if (instalado || typeof window === 'undefined') return;
  instalado = true;
  const original = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = urlDe(input);
    if (!esDelServidor(url)) return original(input, init);
    const token = tokenSesion();
    let resp: Response;
    if (token) {
      const headers = new Headers(init?.headers || (input instanceof Request ? input.headers : undefined));
      if (!headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`);
      resp = await original(input, { ...(init || {}), headers });
    } else {
      resp = await original(input, init);
    }
    // Solo el 401 del control de sesión cierra la sesión (otras rutas pueden
    // responder 401 por motivos propios, ej. un dispositivo no vinculado).
    if (resp.status === 401 && token) {
      const datos = await resp.clone().json().catch(() => null);
      if (datos?.codigo === 'sesion_requerida') {
        try { localStorage.removeItem(CLAVE_USUARIO); } catch {}
        window.dispatchEvent(new Event(EVENTO_SESION_VENCIDA));
      }
    }
    return resp;
  };
}

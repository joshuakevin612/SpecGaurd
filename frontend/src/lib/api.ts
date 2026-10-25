// This address is deployment configuration, never a browser-storage redirect target.
export const API_URL = (import.meta.env.VITE_API_URL || (import.meta.env.PROD ? '/api' : 'http://127.0.0.1:8000')).replace(/\/+$/, '');

let csrf = '';
export function setCsrf(value: string) { csrf = value; }
export async function apiRequest<T>(path: string, body?: unknown, method?: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: method || (body === undefined ? 'GET' : 'POST'),
      headers: { 'Content-Type': 'application/json', 'X-SpecGuard-Client': 'web', 'X-CSRF-Token': csrf },
      credentials: 'include', redirect: 'error', signal: AbortSignal.timeout(165000),
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch {
    throw new Error('The connection was interrupted. Check the project report before retrying; the run may still be finishing.');
  }
  if (response.status === 401 && !path.startsWith('/auth/')) window.dispatchEvent(new Event('session-expired'));
  const data = response.status === 204 ? undefined : await response.json().catch(() => undefined);
  if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : `Request failed (${response.status}). Try again or contact support.`);
  return data as T;
}

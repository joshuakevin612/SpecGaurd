export type HealthState = 'idle' | 'checking' | 'connected' | 'unreachable';

export async function checkBackendHealth(baseUrl: string): Promise<void> {
  const normalized = baseUrl.trim().replace(/\/+$/, '');
  if (!normalized) throw new Error('Enter a backend URL to check the connection.');
  let response: Response;
  try {
    response = await fetch(`${normalized}/health`, {
      method: 'GET',
      headers: { Accept: '*/*' },
      credentials: 'include',
      signal: AbortSignal.timeout(7000),
    });
  } catch {
    throw new Error('Could not reach the backend. Check the address and that the server is running.');
  }
  if (!response.ok) {
    throw new Error(`The backend responded with HTTP ${response.status}.`);
  }
}

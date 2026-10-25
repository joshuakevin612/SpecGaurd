import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { Link, useLocation } from 'wouter';
import { UserRound } from 'lucide-react';
import { apiRequest, setCsrf } from '@/lib/api';

type User = { id: string; username: string };
type Session = { user: User; csrf: string; recovery_code?: string };
const Account = createContext<{ user?: User; loading: boolean; sessionError: string; enter: (session: Session) => void; exit: () => void }>({ loading: true, sessionError: '', enter() {}, exit() {} });
export const useAccount = () => useContext(Account);

export function clearDrafts() {
  try {
    for (const store of [localStorage, sessionStorage]) {
      store.removeItem('specguard-specification');
      store.removeItem('specguard-source-code');
    }
  } catch { /* Storage may be disabled; drafts are never required. */ }
}

export function AccountProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User>();
  const [loading, setLoading] = useState(true);
  const [sessionError, setSessionError] = useState('');
  const enter = (s: Session) => { setUser(s.user.id === 'local' ? undefined : s.user); setCsrf(s.csrf); setSessionError(''); };
  const exit = () => { setUser(undefined); setCsrf(''); clearDrafts(); };
  useEffect(() => {
    let alive = true;
    apiRequest<Session>('/auth/session').then(s => { if (alive) enter(s); })
      .catch(e => { if (alive && !String(e.message).includes('Sign in')) setSessionError(e.message); })
      .finally(() => { if (alive) setLoading(false); });
    window.addEventListener('session-expired', exit);
    return () => { alive = false; window.removeEventListener('session-expired', exit); };
  }, []);
  return <Account.Provider value={{ user, loading, sessionError, enter, exit }}>{children}</Account.Provider>;
}

export function RequireAccount({ children }: { children: ReactNode }) {
  const { user, loading } = useAccount();
  const [location, navigate] = useLocation();
  useEffect(() => {
    if (!loading && !user) navigate(`/login?next=${encodeURIComponent(location)}`, { replace: true });
  }, [user, loading, location, navigate]);
  if (loading || !user) return <p role="status">Checking your session...</p>;
  return children;
}

export function PrivacyNotice() {
  return <details className="privacy-notice">
    <summary>Privacy, limits and account recovery</summary>
    <p>Specifications, code and test evidence are stored on this server. Live verification sends submitted content to the configured NVIDIA or Nebius model provider. Do not submit credentials or code you are not permitted to share.</p>
    <p>Generated cases provide finite behavioral evidence, not formal proof. Only synchronous top-level Python functions with JSON inputs and outputs are supported. Proposed fixes require retesting. Untrusted code runs in resource-limited containers.</p>
    <p>You can download reports, delete projects, or delete your account and its active data. Backup deletion follows the deployment operator's retention policy. This service uses an essential session cookie lasting up to eight hours; source drafts are not saved automatically.</p>
    <p>Accounts use a username, not an email address. Save your recovery code with your password. It lets you reset a forgotten password and is replaced after use. There is no email password recovery.</p>
    <p>Default limits: 20 projects and 20 verification attempts per account per day. One verification runs at a time; busy requests can be retried later. Service limits may be adjusted by the operator.</p>
  </details>;
}

export function AuthGate() {
  const { user, loading, enter, sessionError } = useAccount();
  const [, navigate] = useLocation();
  const requested = new URLSearchParams(window.location.search).get('next') || '/';
  const destination = /^\/(verify|projects|reports)(\/[^?#]*)?$/.test(requested) ? requested : '/';
  const [signup, setSignup] = useState(false);
  const [recovering, setRecovering] = useState(false);
  const [recoveryInput, setRecoveryInput] = useState('');
  const [savedRecovery, setSavedRecovery] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (user && !savedRecovery) navigate(destination, { replace: true }); }, [user, savedRecovery, destination, navigate]);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const s = await apiRequest<Session>(recovering ? '/auth/recover' : signup ? '/auth/signup' : '/auth/login',
        { username, password, ...(recovering ? { recovery_code: recoveryInput } : {}) });
      setSavedRecovery(s.recovery_code || ''); enter(s); setPassword(''); setRecoveryInput('');
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not sign in. Try again.'); }
    finally { setBusy(false); }
  };
  if (loading) return <p role="status">Checking your session...</p>;
  if (user && savedRecovery) return <div className="account-page"><div className="account-form">
    <h1 className="page-title">Save your recovery code.</h1>
    <p>This code can reset your password. It is shown once. Keep it somewhere private, separate from this browser.</p>
    <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{savedRecovery}</pre>
    <button className="btn btn-primary" onClick={() => setSavedRecovery('')}>I have saved my recovery code</button>
  </div></div>;
  if (user) return <p role="status">Opening your workspace...</p>;
  return <div className="account-page"><div className="account-form">
    <Link href="/" className="account-home-link">Back to homepage</Link>
    <h1 className="page-title">{recovering ? 'Recover your account.' : signup ? 'Create your workspace.' : 'Log in to SpecGuard.'}</h1>
    <p>Test Python functions against written requirements and inspect the evidence.</p>
    <form onSubmit={submit}>
      <label htmlFor="username">Username</label>
      <input id="username" className="form-input-text" autoComplete="username" required minLength={3} maxLength={32}
        pattern="[a-zA-Z0-9_]+" value={username} onChange={e => setUsername(e.target.value)} aria-describedby="username-help" />
      <p id="username-help">3-32 letters, numbers or underscores.</p>
      <label htmlFor="password">Password</label>
      <input id="password" className="form-input-text" type="password" autoComplete={signup || recovering ? 'new-password' : 'current-password'}
        required minLength={12} maxLength={128} value={password} onChange={e => setPassword(e.target.value)} aria-describedby="password-help" />
      <p id="password-help">{recovering ? 'Choose a new password with at least 12 characters.' : 'At least 12 characters. Save it securely.'}</p>
      {recovering && <><label htmlFor="recovery-code">Recovery code</label>
        <input id="recovery-code" className="form-input-text" required autoComplete="off" value={recoveryInput} onChange={e => setRecoveryInput(e.target.value)} /></>}
      {signup && <label className="consent-row"><input type="checkbox" required /> I have read the privacy and service limits below.</label>}
      {(error || sessionError) && <p role="alert" className="account-error">{error || sessionError}</p>}
      <button className="btn btn-primary" disabled={busy} type="submit">{busy ? 'Please wait...' : recovering ? 'Reset password' : signup ? 'Create account' : 'Log in'}</button>
      <button className="btn btn-secondary" disabled={busy} type="button" onClick={() => { setSignup(!signup); setRecovering(false); setError(''); setPassword(''); }}>
        {signup ? 'Use an existing account' : 'Create an account'}
      </button>
      {!signup && <button className="btn btn-ghost" type="button" disabled={busy} onClick={() => { setRecovering(!recovering); setError(''); setPassword(''); }}>{recovering ? 'Back to log in' : 'Use a recovery code'}</button>}
    </form>
    <PrivacyNotice />
  </div></div>;
}

export function AccountControls() {
  const { user, exit } = useAccount();
  const [, navigate] = useLocation();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const act = async (remove = false) => {
    if (remove && !window.confirm('Delete your account and all active projects and reports? This cannot be undone.')) return;
    setBusy(true); setError('');
    try { await apiRequest(remove ? '/auth/account' : '/auth/logout', undefined, remove ? 'DELETE' : 'POST'); exit(); navigate('/'); }
    catch (e) { setError(e instanceof Error ? e.message : 'Account action failed'); }
    finally { setBusy(false); }
  };
  if (!user) return <Link href="/login" className="btn btn-ghost btn-sm login-link">Log in</Link>;
  return <div className="account-controls">
    <span>{user.username}</span>
    <button className="btn btn-ghost btn-sm logout-button" disabled={busy} onClick={() => act()}>Log out</button>
    <details><summary aria-label="Account and privacy" title="Account and privacy"><UserRound size={17} /></summary>
      <p>Signed in as {user.username}</p><PrivacyNotice />
      <button className="btn btn-secondary" disabled={busy} onClick={() => act()}>Log out</button>
      <button className="btn btn-secondary" disabled={busy} onClick={() => act(true)}>Delete account and data</button>
    </details>
    {error && <p role="alert">{error}</p>}
  </div>;
}

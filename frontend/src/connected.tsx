import { useEffect, useState, useMemo, useRef } from 'react';
import { Link, useLocation } from 'wouter';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import {
  ShieldCheck, AlertTriangle, CheckCircle2, XCircle, ArrowRight,
  FileCode2, FileText, Play, RefreshCw, Download, Sparkles,
  Search, Terminal, Check, Layers, Code2, AlertCircle, ArrowLeft,
  ChevronRight, ChevronDown, Pencil, Cpu, FlaskConical, Clock, Compass
} from 'lucide-react';
import { VerificationIntro } from './components/verification-intro';
import { MethodSequence } from './components/method-sequence';
import { CodeEditor } from './components/code-editor';
import { VerificationPipelineStepper, type PipelineStage } from './components/verification-pipeline-stepper';
import { SlidingTabs, type TabItem } from './components/sliding-tabs';
import { AnimatedCounter } from './components/animated-counter';
import { MagneticButton } from './components/magnetic-button';

import { apiRequest } from './lib/api';
import { clearDrafts, PrivacyNotice, useAccount } from './components/account';

const request = apiRequest;

export type Project = {
  id: string;
  name?: string;
  specification?: string;
  source_code?: string;
  created_at?: string;
  updated_at?: string;
};

export type Report = {
  error?: string;
  status: string;
  project_id: string;
  summary: {
    verified?: boolean;
    passed?: number;
    failed?: number;
    errors?: number;
    timeouts?: number;
    flaky?: number;
    total_requirements?: number;
    [key: string]: unknown;
  };
  requirements: Array<{
    id: string;
    text: string;
    ambiguous: boolean;
    clarification_note?: string;
  }>;
  tests: Array<{
    id: string;
    requirement_id: string;
    description: string;
    pytest_code: string;
  }>;
  test_results: Array<{
    test_id: string;
    requirement_id: string;
    status: string;
    output: string;
    duration_ms: number;
  }>;
  static_findings: Array<{
    line: number;
    message: string;
  }>;
  fix_suggestions: Array<{
    requirement_id: string;
    explanation: string;
    patched_code: string;
  }>;
  requirement_states: Array<{
    requirement_id: string;
    state: string;
  }>;
};

function ErrorBanner({ message }: { message: string }) {
  if (!message) return null;
  return (
    <motion.div
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      role="alert"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        padding: '14px 18px',
        borderRadius: 'var(--r-md)',
        background: 'var(--status-fail-bg)',
        border: '1px solid var(--status-fail-border)',
        color: 'var(--status-fail)',
        marginBottom: 'var(--s-5)',
      }}
    >
      <AlertCircle size={18} style={{ flexShrink: 0 }} />
      <span style={{ fontSize: 'var(--text-sm)', lineHeight: 1.5 }}>{message}</span>
    </motion.div>
  );
}

function useProjects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    request<{ projects: Project[] }>('/projects')
      .then((data) => {
        if (alive) setProjects(data.projects || []);
      })
      .catch((e) => {
        if (alive) setError(e instanceof Error ? e.message : 'Could not fetch projects');
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  return { projects, error, loading };
}

/* ───────── 1. CONNECTED DASHBOARD ───────── */
export function ConnectedDashboard() {
  const { user, loading } = useAccount();
  return <div className="page-content">
    <VerificationIntro />
    <MethodSequence />
    {user ? <DashboardProjects /> : <section id="workspace" className="public-workspace">
      <h2>Your verification workspace</h2>
      <p>Log in to create verifications and access your saved projects and reports.</p>
      {loading ? <p role="status">Checking your session...</p> : <Link href="/login" className="btn btn-primary">Log in to your workspace <ArrowRight size={16} /></Link>}
    </section>}
  </div>;
}

function DashboardProjects() {
  const { projects, error, loading } = useProjects();
  const reduceMotion = useReducedMotion() ?? false;

  return (
    <div className="page-content">

      {/* Recent Projects Ledger Table */}
      <div id="workspace" className="panel projects-panel" style={{ padding: '0', overflow: 'hidden' }}>
        <div style={{ padding: 'var(--s-4) var(--s-5)', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h2 style={{ fontSize: '1.3rem' }}>Recent Verification Projects</h2>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--muted)' }}>
              Your saved specifications and verification reports
            </div>
          </div>
          <Link href="/projects" className="btn btn-ghost btn-sm">
            <span>View all projects</span>
            <ArrowRight size={14} />
          </Link>
        </div>

        {loading ? (
          <div style={{ padding: 'var(--s-6)', textAlign: 'center', color: 'var(--muted)' }}>
            Loading workspace records…
          </div>
        ) : error ? (
          <div className="workspace-load-error">
            <AlertCircle size={24} aria-hidden="true" />
            <h3>Projects could not be loaded</h3>
            <ErrorBanner message={error} />
            <Link href="/projects" className="btn btn-secondary">Open projects to retry <ArrowRight size={16} /></Link>
          </div>
        ) : projects.length === 0 ? (
          <div className="workspace-empty" style={{ padding: 'var(--s-7) var(--s-5)', textAlign: 'center' }}>
            <div
              style={{
                width: '44px',
                height: '44px',
                borderRadius: 'var(--r-md)',
                background: 'var(--surface-raised)',
                border: '1px solid var(--line)',
                margin: '0 auto var(--s-3)',
                display: 'grid',
                placeItems: 'center',
                color: 'var(--accent)',
              }}
            >
              <FileCode2 size={20} />
            </div>
            <h3 style={{ fontSize: '1.2rem', marginBottom: 'var(--s-2)' }}>No projects verified yet</h3>
            <p style={{ color: 'var(--muted)', fontSize: 'var(--text-sm)', margin: '0 auto var(--s-4)', maxWidth: '42ch' }}>
              Create your first verification by specifying expected behavior and providing Python code.
            </p>
            <Link href="/verify" className="btn btn-primary">
              <ShieldCheck size={16} />
              <span>Create first verification</span>
            </Link>
          </div>
        ) : (
          <div className="ledger-table-wrap" style={{ border: 0, borderRadius: 0 }}>
            <table className="ledger-table">
              <thead>
                <tr>
                  <th>PROJECT</th>
                  <th>SPECIFICATION PREVIEW</th>
                  <th>LAST UPDATED</th>
                  <th style={{ textAlign: 'right' }}>ACTION</th>
                </tr>
              </thead>
              <tbody>
                {projects.slice(0, 5).map((project) => (
                  <tr key={project.id}>
                    <td>
                      <Link href={`/projects/${encodeURIComponent(project.id)}`} className="table-link">
                        <FileText size={15} style={{ color: 'var(--accent)' }} />
                        <span className="project-identity"><strong>{project.name || 'Untitled project'}</strong><span className="mono">{project.id}</span></span>
                      </Link>
                    </td>
                    <td>
                      <span style={{ color: 'var(--muted)', fontSize: 'var(--text-xs)', display: 'block', maxWidth: '380px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {project.specification
                          ? `${project.specification.replace(/#+\s*/g, '').slice(0, 75)}…`
                          : 'Saved verification project'}
                      </span>
                    </td>
                    <td>
                      <span className="mono" style={{ color: 'var(--muted)', fontSize: 'var(--text-xs)' }}>
                        {project.updated_at ? new Date(project.updated_at).toLocaleString() : 'Recent'}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <Link href={`/reports/${encodeURIComponent(project.id)}`} className="btn btn-secondary btn-sm">
                        <span>Report</span>
                        <ArrowRight size={13} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

/* ───────── 2. CONNECTED VERIFY WORKSPACE ───────── */
export function ConnectedVerify() {
  const [, navigate] = useLocation();
  const [projectName, setProjectName] = useState('');
  const [specification, setSpec] = useState('');
  const [code, setCode] = useState('');
  const { user } = useAccount();
  const reduceMotion = useReducedMotion() ?? false;
  const denialKey = `specguard-consent-denied:${user?.id || 'guest'}`;
  const [consent, setConsent] = useState<'pending' | 'accepted' | 'denied'>(() => {
    try { return sessionStorage.getItem(denialKey) === 'true' ? 'denied' : 'pending'; } catch { return 'pending'; }
  });
  const [consentOpen, setConsentOpen] = useState(false);
  const [consentMessage, setConsentMessage] = useState('');
  const consentSection = useRef<HTMLElement>(null);
  const consentAccept = useRef<HTMLButtonElement>(null);
  const consentTrigger = useRef<HTMLButtonElement>(null);
  const revealConsent = useRef(false);
  const scrollToConsent = () => {
    consentAccept.current?.focus({ preventScroll: true });
    consentSection.current?.scrollIntoView({ behavior: reduceMotion ? 'instant' : 'smooth', block: 'start' });
  };
  const requestConsent = () => {
    setConsentMessage('Accept the sharing notice below before running verification.');
    if (consent === 'denied') return;
    if (consentOpen) scrollToConsent();
    else { revealConsent.current = true; setConsentOpen(true); }
  };
  const decideConsent = (decision: 'accepted' | 'denied') => {
    setConsent(decision);
    try {
      if (decision === 'denied') sessionStorage.setItem(denialKey, 'true');
      else sessionStorage.removeItem(denialKey);
    } catch { /* The in-memory decision still applies when storage is unavailable. */ }
    revealConsent.current = false;
    setConsentMessage(decision === 'accepted'
      ? 'Accepted. You can now click Verify specification to start.'
      : 'Denied. Nothing will be submitted. You can reopen this section and accept later.');
    setConsentOpen(false);
    consentTrigger.current?.focus({ preventScroll: true });
  };
  const [capabilities, setCapabilities] = useState<{provider: string; runner: string}>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [projectId, setProjectId] = useState<string>();
  const [submitted, setSubmitted] = useState<{ specification: string; code: string; name: string }>();
  const [activeStage, setActiveStage] = useState<PipelineStage>('ingestion');

  useEffect(() => {
    request<{provider: string; runner: string}>('/capabilities').then(setCapabilities).catch(() => {});
  }, []);

  const loadCartDemo = async () => {
    setError('');
    try {
      const demo = await request<{ specification: string; source_code: string }>('/demos/cart');
      setSpec(demo.specification);
      setCode(demo.source_code);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load demo from backend');
    }
  };

  const loadRateLimiterDemo = () => {
    setError('');
    setSpec(`# Token Bucket Rate Limiter Specification
1. Limiter is initialized with max_tokens (positive int) and refill_rate (tokens/sec).
2. Calling allow_request(cost) returns True if bucket has at least cost tokens, then deducts cost.
3. If tokens < cost, allow_request returns False and tokens are unchanged.
4. Tokens automatically refill based on elapsed time up to max_tokens capacity.
5. Non-positive cost raises ValueError.`);
    setCode(`import time

class TokenBucketLimiter:
    def __init__(self, max_tokens: int, refill_rate: float):
        if max_tokens <= 0 or refill_rate <= 0:
            raise ValueError("Parameters must be positive")
        self.capacity = float(max_tokens)
        self.tokens = float(max_tokens)
        self.refill_rate = refill_rate
        self.last_check = time.time()

    def allow_request(self, cost: int = 1) -> bool:
        if cost <= 0:
            raise ValueError("Cost must be positive")
        now = time.time()
        elapsed = now - self.last_check
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_check = now

        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False
`);
  };

  const submit = async () => {
    if (consent !== 'accepted') { requestConsent(); return; }
    setBusy(true);
    setError('');
    setActiveStage('ingestion');

    try {
      const name = projectName.trim() || 'Untitled project';
      let id = projectId;
      if (!id || submitted?.specification !== specification || submitted?.code !== code) {
        const result = await request<{ project_id: string }>('/projects', {
          name,
          specification,
          source_code: code,
        });
        id = result.project_id;
        setProjectId(id);
        setSubmitted({ specification, code, name });
      } else if (submitted?.name !== name) {
        await request(`/projects/${id}`, { name }, 'PATCH');
        setSubmitted({ specification, code, name });
      }

      setActiveStage('synthesis');
      // Execute verification
      await request(`/projects/${id}/verify`, {});
      setActiveStage('evidence');

      navigate(`/reports/${id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Verification run failed. Check server status and try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page-content">
      <div className="page-header-row">
        <div className="page-header-content">
          <h1 className="page-title">Put the specification first.</h1>
          <p className="page-description">
            Provide the observable behavioral contract and Python implementation. SpecGuard
            synthesizes requirement-anchored pytest suites, executes them in a sandbox, and saves
            test-based evidence. Supported inputs are synchronous top-level functions with JSON inputs and outputs.
          </p>
        </div>
        <div className="page-actions">
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={busy}
            onClick={loadCartDemo}
            title="Load shopping cart example specification & code"
          >
            <Sparkles size={14} style={{ color: 'var(--accent)' }} />
            <span>Load cart demo</span>
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={busy}
            onClick={loadRateLimiterDemo}
            hidden
            title="Load token bucket limiter example"
          >
            <Code2 size={14} />
            <span>Load rate limiter demo</span>
          </button>
        </div>
      </div>

      <ErrorBanner message={error} />

      <div className="project-name-field">
        <label className="form-label" htmlFor="new-project-name">Project name <span>(optional)</span></label>
        <input id="new-project-name" className="form-input-text" value={projectName} onChange={event => setProjectName(event.target.value)}
          maxLength={100} disabled={busy} placeholder="e.g. Shopping cart validation" aria-describedby="project-name-help" />
        <p id="project-name-help">Up to 100 characters. Leave blank to use “Untitled project”. You can rename it later.</p>
      </div>

      {/* Interactive Verification Pipeline Stepper */}
      <VerificationPipelineStepper
        activeStage={activeStage}
        isRunning={busy}
        onSelectStage={setActiveStage}
      />

      {/* Split Workspace: Spec & Python Source */}
      <div className="verify-workspace-grid">
        {/* Left: Written Specification */}
        <div className="panel spec-editor-card" style={{ padding: 0, overflow: 'hidden' }}>
          <div className="editor-header-bar">
            <div className="editor-title-group">
              <FileText size={16} style={{ color: 'var(--accent)' }} />
              <span>Written Specification (Markdown / Plaintext)</span>
            </div>
            <div className="editor-actions-group">
              <label
                className="btn btn-ghost btn-sm"
                style={{ cursor: busy ? 'not-allowed' : 'pointer' }}
                title="Import specification from file"
              >
                <span>Import spec</span>
                <input
                  type="file"
                  accept=".md,.txt,text/plain,text/markdown"
                  style={{ display: 'none' }}
                  disabled={busy}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file && file.size > 60000) { setError('The specification file must be 60 KB or smaller.'); return; }
                    if (file) {
                      void file.text().then(setSpec).catch(() => setError('Could not read specification file'));
                    }
                  }}
                />
              </label>
            </div>
          </div>

          <textarea
            id="spec-input"
            className="spec-textarea"
            disabled={busy}
            value={specification}
            onChange={(e) => setSpec(e.target.value)}
            placeholder={`# Module Specification\n1. State clear preconditions and observable invariants.\n2. Document error handling and edge cases.\n3. Every numbered rule becomes an evaluated requirement.`}
            aria-label="Written specification requirements"
          />

          <div className="editor-statusbar">
            <span>Markdown / Text formatted</span>
            <span className="mono">
              {specification.split('\n').filter((l) => l.trim().length > 0).length} lines · {specification.length} characters
            </span>
          </div>
        </div>

        {/* Right: Python Source Code */}
        <div className="code-editor-card">
          <CodeEditor
            value={code}
            onChange={setCode}
            disabled={busy}
            placeholder="# Provide the Python class or functions implementing the specification"
          />
        </div>
      </div>

      {/* Execution Control Footer */}
      <div
        className="panel execution-footer"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 'var(--s-4)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s-3)' }}>
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: 'var(--r-sm)',
              background: busy ? 'var(--status-warn-bg)' : 'var(--surface-raised)',
              border: `1px solid ${busy ? 'var(--status-warn-border)' : 'var(--line)'}`,
              display: 'grid',
              placeItems: 'center',
              color: busy ? 'var(--status-warn)' : 'var(--muted)',
            }}
          >
            {busy ? <RefreshCw size={17} className="animate-spin" /> : <ShieldCheck size={18} />}
          </div>
          <div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--ink)' }}>
              {busy ? 'Generating and running behavioral cases…' : 'Ready to verify specification'}
            </div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--muted)' }}>
              {busy
                ? 'Generation and execution may take a moment. Avoid resubmitting while this run is active.'
                : capabilities?.runner === 'trusted-local' ? 'Trusted local mode uses this machine’s permissions. Only run code you trust.' : 'Execution takes place in resource-limited containers; expected answers stay in the supervisor.'}
            </div>
          </div>
        </div>

        <MagneticButton
          type="button"
          className="btn btn-primary"
          style={{ minWidth: '180px' }}
          disabled={busy || !specification.trim() || !code.trim()}
          onClick={submit}
        >
          {busy ? (
            <>
              <RefreshCw size={15} className="animate-spin" />
              <span>Verifying…</span>
            </>
          ) : (
            <>
              <Play size={15} />
              <span>Verify specification</span>
            </>
          )}
        </MagneticButton>
        {consentMessage && <p className="verification-consent-message" role="status">{consentMessage}</p>}
      </div>

      <section ref={consentSection} className="verification-disclosure consent-footer" aria-labelledby="consent-heading">
        <h2 id="consent-heading">
          <button ref={consentTrigger} type="button" className="consent-disclosure-trigger" aria-expanded={consentOpen} aria-controls="verification-consent-body"
            onClick={() => { revealConsent.current = false; setConsentOpen(open => !open); }}>
            <span>Privacy and code sharing</span>
            <span className="consent-disclosure-meta">{consent === 'accepted' ? 'Accepted' : consent === 'denied' ? 'Denied' : 'Review before verifying'}<ChevronDown size={18} aria-hidden="true" /></span>
          </button>
        </h2>
        <motion.div id="verification-consent-body" className="consent-disclosure-body" initial={false}
          animate={{ height: consentOpen ? 'auto' : 0, opacity: consentOpen ? 1 : 0 }}
          transition={{ duration: reduceMotion ? 0 : .35, ease: [.16, 1, .3, 1] }}
          inert={!consentOpen || undefined} aria-hidden={!consentOpen}
          onAnimationComplete={() => { if (revealConsent.current && consentOpen) { revealConsent.current = false; scrollToConsent(); } }}>
          <div className="consent-disclosure-content">
            <p className="consent-provider">{capabilities ? `Provider: ${capabilities.provider === 'mock' ? 'MOCK — bundled demonstrations only' : capabilities.provider}. Execution: ${capabilities.runner}.` : 'Checking provider configuration…'}</p>
            <p>I may share this specification and code with the configured provider. I have removed secrets.</p>
            <PrivacyNotice />
            <div className="consent-decision-actions">
              <button ref={consentAccept} type="button" className="btn btn-primary" disabled={busy} onClick={() => decideConsent('accepted')}>Accept</button>
              <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => decideConsent('denied')}>Deny</button>
            </div>
            <button type="button" className="btn btn-ghost btn-sm consent-clear" disabled={busy} onClick={() => { clearDrafts(); setSpec(''); setCode(''); }}>Clear inputs and old browser drafts</button>
          </div>
        </motion.div>
      </section>
    </div>
  );
}

/* ───────── 3. CONNECTED LISTINGS (PROJECTS / REPORTS) ───────── */
export function ConnectedListing({ kind }: { kind: 'projects' | 'reports' }) {
  const { projects, error, loading } = useProjects();
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return projects.filter((p) => `${p.name || 'Untitled project'} ${p.id}`.toLowerCase().includes(query));
  }, [projects, search]);

  const title = kind === 'projects' ? 'Verification Projects' : 'Verification Reports';
  const desc =
    kind === 'projects'
      ? 'Manage and inspect all saved specification models and Python source suites.'
      : 'Review test execution evidence, requirement compliance, and proposed patches.';

  return (
    <div className="page-content">
      <div className="page-header-row">
        <div className="page-header-content">
          <h1 className="page-title">{title}</h1>
          <p className="page-description">{desc}</p>
        </div>
        <div className="page-actions">
          <Link href="/verify" className="btn btn-primary">
            <ShieldCheck size={16} />
            <span>New verification</span>
          </Link>
        </div>
      </div>

      <ErrorBanner message={error} />

      {/* Search Bar */}
      <div style={{ marginBottom: 'var(--s-5)', maxWidth: '420px' }}>
        <label className="form-label" htmlFor="project-search">
          Find a project
        </label>
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
          <Search size={16} style={{ position: 'absolute', left: '12px', color: 'var(--muted)' }} />
          <input
            id="project-search"
            className="form-input-text"
            style={{ paddingLeft: '38px' }}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name or project ID…"
          />
        </div>
      </div>

      {/* Table */}
      <div className="panel" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 'var(--s-6)', textAlign: 'center', color: 'var(--muted)' }}>
            Loading records…
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: 'var(--s-7) var(--s-5)', textAlign: 'center' }}>
            <FileCode2 size={24} style={{ color: 'var(--muted)', margin: '0 auto var(--s-2)' }} />
            <h3 style={{ fontSize: '1.2rem', marginBottom: 'var(--s-1)' }}>
              {search ? 'No matching projects found' : 'No projects recorded yet'}
            </h3>
            <p style={{ color: 'var(--muted)', fontSize: 'var(--text-sm)', marginBottom: 'var(--s-4)' }}>
              {search ? 'Try adjusting your search query.' : 'Run a verification to save your first project.'}
            </p>
            {!search && (
              <Link href="/verify" className="btn btn-primary btn-sm">
                <span>Start verification</span>
              </Link>
            )}
          </div>
        ) : (
          <div className="ledger-table-wrap" style={{ border: 0, borderRadius: 0 }}>
            <table className="ledger-table">
              <thead>
                <tr>
                  <th>PROJECT</th>
                  <th>SPECIFICATION PREVIEW</th>
                  <th>SOURCE SIZE</th>
                  <th>LAST UPDATED</th>
                  <th style={{ textAlign: 'right' }}>EVIDENCE</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((project) => (
                  <tr key={project.id}>
                    <td>
                      <Link href={`/${kind}/${encodeURIComponent(project.id)}`} className="table-link">
                        <FileText size={15} style={{ color: 'var(--accent)' }} />
                        <span className="project-identity"><strong>{project.name || 'Untitled project'}</strong><span className="mono">{project.id}</span></span>
                      </Link>
                    </td>
                    <td>
                      <span style={{ color: 'var(--muted)', fontSize: 'var(--text-xs)', display: 'block', maxWidth: '340px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {project.specification
                          ? `${project.specification.replace(/#+\s*/g, '').slice(0, 65)}…`
                          : 'Saved verification project'}
                      </span>
                    </td>
                    <td>
                      <span className="mono" style={{ fontSize: 'var(--text-xs)', color: 'var(--muted)' }}>
                        {project.source_code ? `${project.source_code.split('\n').length} lines` : 'Python source'}
                      </span>
                    </td>
                    <td>
                      <span className="mono" style={{ fontSize: 'var(--text-xs)', color: 'var(--muted)' }}>
                        {project.updated_at ? new Date(project.updated_at).toLocaleString() : 'Recent'}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <Link href={`/reports/${encodeURIComponent(project.id)}`} className="btn btn-secondary btn-sm">
                        <span>Inspect report</span>
                        <ArrowRight size={13} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

/* ───────── 4. CONNECTED DETAIL (PROJECT / REPORT) ───────── */
export function ConnectedDetail({ id, kind }: { id?: string; kind: 'project' | 'report' }) {
  const [, navigate] = useLocation();
  const [projectName, setProjectName] = useState('');
  const [nameDraft, setNameDraft] = useState('');
  const [renaming, setRenaming] = useState(false);
  const [savingName, setSavingName] = useState(false);
  const [nameError, setNameError] = useState('');
  const [nameStatus, setNameStatus] = useState('');
  const [report, setReport] = useState<Report>();
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'evidence' | 'tests' | 'findings' | 'fixes' | 'retest'>('evidence');

  const load = async () => {
    if (!id) return;
    const [project, data] = await Promise.all([
      request<Project>(`/projects/${id}`),
      request<{ report: Report }>(`/projects/${id}/report`),
    ]);
    setProjectName(project.name || 'Untitled project');
    setNameDraft(project.name || 'Untitled project');
    setCode(project.source_code || '');
    setReport(data.report);
  };

  useEffect(() => {
    setLoading(true);
    setError('');
    void load()
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load report evidence'))
      .finally(() => setLoading(false));
  }, [id]);

  const saveName = async (event: React.FormEvent) => {
    event.preventDefault();
    const name = nameDraft.trim();
    if (!name || name.length > 100) { setNameError('Enter a project name between 1 and 100 characters.'); return; }
    setSavingName(true); setNameError(''); setNameStatus('');
    try {
      const project = await request<Project>(`/projects/${id}`, { name }, 'PATCH');
      setProjectName(project.name || name); setNameDraft(project.name || name); setRenaming(false);
      setNameStatus('Project name saved.');
    } catch (e) { setNameError(e instanceof Error ? e.message : 'Could not rename project. Try again.'); }
    finally { setSavingName(false); }
  };

  const retest = async () => {
    setBusy(true);
    setError('');
    try {
      await request(`/projects/${id}/retest`, { updated_code: code });
      await load();
      setActiveTab('evidence');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Retest failed');
    } finally {
      setBusy(false);
    }
  };

  const downloadReportJson = () => {
    if (!report) return;
    const blob = new Blob([JSON.stringify({ ...report, project_name: projectName }, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `specguard-${id}-report.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const isVerified = report?.summary?.verified === true;
  const isNotRun = report?.status === 'not_run';

  const requirements = report?.requirements || [];
  const tests = report?.tests || [];
  const testResults = report?.test_results || [];
  const staticFindings = report?.static_findings || [];
  const fixSuggestions = report?.fix_suggestions || [];
  const requirementStates = report?.requirement_states || [];

  const tabs: TabItem<'evidence' | 'tests' | 'findings' | 'fixes' | 'retest'>[] = [
    {
      id: 'evidence',
      label: 'Requirements & Traceability',
      badge: requirements.length,
      icon: <Layers size={14} />,
    },
    {
      id: 'tests',
      label: 'Test Cases & Observations',
      badge: tests.length,
      icon: <Terminal size={14} />,
    },
    {
      id: 'findings',
      label: 'Static Analysis',
      badge: staticFindings.length,
      icon: <AlertTriangle size={14} />,
    },
    {
      id: 'fixes',
      label: 'Synthesized Patches',
      badge: fixSuggestions.length,
      icon: <Sparkles size={14} />,
    },
    {
      id: 'retest',
      label: 'Retest Sandbox',
      icon: <RefreshCw size={14} />,
    },
  ];

  return (
    <div className="page-content">
      {/* Back button link */}
      <div style={{ marginBottom: 'var(--s-4)' }}>
        <Link href={kind === 'project' ? '/projects' : '/reports'} className="btn btn-ghost btn-sm">
          <ArrowLeft size={14} />
          <span>Back to {kind === 'project' ? 'projects' : 'reports'}</span>
        </Link>
      </div>

      <div className="page-header-row">
        <div className="page-header-content">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <h1 className="page-title project-detail-title">{projectName || id || 'Project'}</h1>
            {report && (
              <span
                className={`status-badge ${isNotRun ? 'neutral' : isVerified ? 'verified' : 'failed'}`}
              >
                {isNotRun ? <Clock size={12} /> : isVerified ? <CheckCircle2 size={12} /> : <AlertTriangle size={12} />}
                <span>{isNotRun ? 'NOT RUN' : isVerified ? 'CASES PASSED' : 'REVIEW REQUIRED'}</span>
              </span>
            )}
          </div>
          <p className="project-detail-id mono">{id}</p>
          <p className="page-description">
            Complete traceability matrix tying written requirements to generated test assertions,
            execution outputs, and proposed fixes that require retesting.
          </p>
        </div>

        <div className="page-actions">
          <button type="button" className="btn btn-secondary btn-sm" disabled={loading || busy || savingName || !!error}
            onClick={() => { setNameDraft(projectName); setRenaming(true); setNameError(''); setNameStatus(''); }}>
            <Pencil size={14} /><span>Rename project</span>
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={downloadReportJson}
            disabled={!report}
            title="Download complete report as JSON"
          >
            <Download size={14} />
            <span>Download JSON</span>
          </button>
          <button className="btn btn-secondary btn-sm" disabled={busy} onClick={async () => {
            if (!window.confirm('Delete this project and its reports permanently?')) return;
            setBusy(true);
            try { await request(`/projects/${id}`, undefined, 'DELETE'); navigate('/projects'); }
            catch (e) { setError(e instanceof Error ? e.message : 'Could not delete project'); }
            finally { setBusy(false); }
          }}>Delete project</button>
        </div>
      </div>

      <ErrorBanner message={error} />

      {renaming && <form className="project-rename-form" onSubmit={saveName}>
        <label className="form-label" htmlFor="project-name-rename">Project name</label>
        <div className="project-rename-controls">
          <input id="project-name-rename" className="form-input-text" value={nameDraft} autoFocus required maxLength={100}
            disabled={savingName} onChange={event => setNameDraft(event.target.value)}
            aria-invalid={!!nameError} aria-describedby={nameError ? 'project-rename-error' : undefined}
            onKeyDown={event => { if (event.key === 'Escape' && !savingName) setRenaming(false); }} />
          <button className="btn btn-primary" type="submit" disabled={savingName || !nameDraft.trim()}>{savingName ? 'Saving…' : 'Save name'}</button>
          <button className="btn btn-secondary" type="button" disabled={savingName} onClick={() => setRenaming(false)}>Cancel</button>
        </div>
        {nameError && <p id="project-rename-error" className="account-error" role="alert">{nameError}</p>}
      </form>}
      {nameStatus && <p className="project-name-status" role="status">{nameStatus}</p>}
      {report?.error && <ErrorBanner message={report.error} />}
      {report && report.status !== 'complete' && report.status !== 'not_run' && <p role="status">Latest run: {report.status}. Earlier evidence below is retained for inspection and does not describe a current passing run.</p>}
      {loading && (
        <div style={{ padding: 'var(--s-8)', textAlign: 'center', color: 'var(--muted)' }}>
          <RefreshCw size={22} className="animate-spin" style={{ margin: '0 auto var(--s-3)' }} />
          <div>Loading verification evidence…</div>
        </div>
      )}

      {report && (
        <>
          {/* Telemetry Ledger Cards */}
          <div className="metrics-ledger">
            <div>
              <div className="metric-card">
                <span className="metric-card-label">
                  <span>PASSED TESTS</span>
                  <CheckCircle2 size={13} style={{ color: 'var(--status-pass)' }} />
                </span>
                <div className="metric-card-val" style={{ color: 'var(--status-pass)' }}>
                  <AnimatedCounter value={Number(report.summary.passed || 0)} />
                </div>
                <span className="metric-card-sub">Passed without assertion error</span>
              </div>
            </div>

            <div>
              <div className="metric-card">
                <span className="metric-card-label">
                  <span>FAILED TESTS</span>
                  <XCircle size={13} style={{ color: 'var(--status-fail)' }} />
                </span>
                <div className="metric-card-val" style={{ color: Number(report.summary.failed) > 0 ? 'var(--status-fail)' : 'var(--muted)' }}>
                  <AnimatedCounter value={Number(report.summary.failed || 0)} />
                </div>
                <span className="metric-card-sub">Violated requirement assertions</span>
              </div>
            </div>

            <div>
              <div className="metric-card">
                <span className="metric-card-label">
                  <span>ERRORS / TIMEOUTS / FLAKY</span>
                  <Clock size={13} style={{ color: 'var(--status-warn)' }} />
                </span>
                <div className="metric-card-val">
                  <AnimatedCounter value={Number(report.summary.errors || 0) + Number(report.summary.timeouts || 0) + Number(report.summary.flaky || 0)} />
                </div>
                <span className="metric-card-sub">Execution boundary violations</span>
              </div>
            </div>

            <div>
              <div className="metric-card">
                <span className="metric-card-label">
                  <span>TOTAL REQUIREMENTS</span>
                  <FileText size={13} style={{ color: 'var(--accent)' }} />
                </span>
                <div className="metric-card-val">
                  <AnimatedCounter value={report.requirements.length} />
                </div>
                <span className="metric-card-sub">Atomic claims evaluated</span>
              </div>
            </div>
          </div>

          {/* Sliding Tabs */}
          <div style={{ marginBottom: 'var(--s-5)' }}>
            <SlidingTabs
              tabs={tabs}
              activeTab={activeTab}
              onChange={(id) => setActiveTab(id)}
            />
          </div>

          {/* TAB 1: REQUIREMENTS & TRACEABILITY MATRIX */}
          {activeTab === 'evidence' && (
            <div className="panel" style={{ padding: 'var(--s-5)' }}>
              <div className="panel-header">
                <div>
                  <h2 className="panel-title">Requirement Traceability Matrix</h2>
                  <div className="panel-subtitle">Every written requirement anchored to executable pytest assertions</div>
                </div>
              </div>

              {requirements.map((req) => {
                const stateObj = requirementStates.find((s) => s.requirement_id === req.id);
                const reqState = stateObj?.state || (req.ambiguous ? 'ambiguous' : 'evaluated');
                const reqTests = tests.filter((t) => t.requirement_id === req.id);

                return (
                  <article key={req.id} className="evidence-card">
                    <div className="evidence-topline">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span className="evidence-id-badge">{req.id}</span>
                        <span
                          className={`status-badge ${
                            reqState === 'passed' || reqState === 'verified'
                              ? 'verified'
                              : reqState === 'failed'
                              ? 'failed'
                              : 'ambiguous'
                          }`}
                        >
                          {reqState}
                        </span>
                      </div>
                      {req.ambiguous && (
                        <span className="status-badge ambiguous">Ambiguous Specification</span>
                      )}
                    </div>

                    <div className="evidence-text">{req.text}</div>

                    {req.clarification_note && (
                      <div
                        style={{
                          marginTop: 'var(--s-2)',
                          padding: 'var(--s-2) var(--s-3)',
                          borderRadius: 'var(--r-xs)',
                          background: 'var(--status-warn-bg)',
                          border: '1px solid var(--status-warn-border)',
                          fontSize: 'var(--text-xs)',
                          color: 'var(--status-warn)',
                        }}
                      >
                        Note: {req.clarification_note}
                      </div>
                    )}

                    {/* Associated tests */}
                    {reqTests.length > 0 && (
                      <div style={{ marginTop: 'var(--s-3)', display: 'grid', gap: 'var(--s-2)' }}>
                        {reqTests.map((test) => {
                          const res = testResults.find((r) => r.test_id === test.id);
                          const passed = res?.status === 'passed';

                          return (
                            <details key={test.id} className="evidence-test-block">
                              <summary className="evidence-test-summary">
                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                                  {passed ? (
                                    <CheckCircle2 size={13} style={{ color: 'var(--status-pass)' }} />
                                  ) : (
                                    <XCircle size={13} style={{ color: 'var(--status-fail)' }} />
                                  )}
                                  <span>{test.description}</span>
                                </span>
                                <span>
                                  {res?.status || 'not run'} ({res?.duration_ms || 0}ms)
                                </span>
                              </summary>
                              <div style={{ marginTop: 'var(--s-3)' }}>
                                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--muted)', marginBottom: '4px' }}>
                                  Generated Pytest Code:
                                </div>
                                <pre className="evidence-code-pre">{test.pytest_code}</pre>
                                {res?.output && (
                                  <>
                                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--muted)', margin: 'var(--s-2) 0 4px' }}>
                                      Execution Output / Traceback:
                                    </div>
                                    <pre className="evidence-code-pre" style={{ color: passed ? 'var(--muted)' : 'var(--status-fail)' }}>
                                      {res.output}
                                    </pre>
                                  </>
                                )}
                              </div>
                            </details>
                          );
                        })}
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          )}

          {/* TAB 2: PYTEST SUITE OUTPUT */}
          {activeTab === 'tests' && (
            <div className="panel">
              <div className="panel-header">
                <div>
                  <h2 className="panel-title">Generated Pytest Execution Log</h2>
                  <div className="panel-subtitle">Raw sandbox output for all executed test functions</div>
                </div>
              </div>

              {testResults.length === 0 ? (
                <div style={{ padding: 'var(--s-6)', textAlign: 'center', color: 'var(--muted)' }}>
                  No test executions recorded.
                </div>
              ) : (
                <div style={{ display: 'grid', gap: 'var(--s-3)' }}>
                  {testResults.map((r, i) => {
                    const testDef = tests.find((t) => t.id === r.test_id);
                    const passed = r.status === 'passed';

                    return (
                      <div key={i} className="evidence-card">
                        <div className="evidence-topline">
                          <span className="mono" style={{ fontSize: 'var(--text-sm)', fontWeight: 600 }}>
                            {r.test_id}: {testDef?.description || 'Test assertion'}
                          </span>
                          <span className={`status-badge ${passed ? 'verified' : 'failed'}`}>
                            {r.status} · {r.duration_ms}ms
                          </span>
                        </div>
                        {r.output && (
                          <pre className="evidence-code-pre" style={{ maxHeight: '280px' }}>
                            {r.output}
                          </pre>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: STATIC FINDINGS */}
          {activeTab === 'findings' && (
            <div className="panel">
              <div className="panel-header">
                <div>
                  <h2 className="panel-title">Static Analysis & Lint Findings</h2>
                  <div className="panel-subtitle">AST checks, unused variables, and syntax hygiene</div>
                </div>
              </div>

              {staticFindings.length === 0 ? (
                <div style={{ padding: 'var(--s-6)', textAlign: 'center' }}>
                  <CheckCircle2 size={24} style={{ color: 'var(--status-pass)', margin: '0 auto var(--s-2)' }} />
                  <h3 style={{ fontSize: '1.2rem', marginBottom: '4px' }}>No static analysis issues found</h3>
                  <p style={{ color: 'var(--muted)', fontSize: 'var(--text-sm)' }}>
                    Python source syntax and basic AST checks passed cleanly.
                  </p>
                </div>
              ) : (
                <div style={{ display: 'grid', gap: 'var(--s-3)' }}>
                  {staticFindings.map((f, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                        padding: 'var(--s-3) var(--s-4)',
                        borderRadius: 'var(--r-md)',
                        background: 'var(--surface-card)',
                        border: '1px solid var(--line)',
                      }}
                    >
                      <span
                        className="mono"
                        style={{
                          padding: '2px 8px',
                          borderRadius: 'var(--r-xs)',
                          background: 'var(--surface-raised)',
                          border: '1px solid var(--line)',
                          color: 'var(--accent)',
                          fontSize: 'var(--text-xs)',
                        }}
                      >
                        Line {f.line}
                      </span>
                      <span style={{ fontSize: 'var(--text-sm)', color: 'var(--ink)' }}>{f.message}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 4: PROPOSED FIXES */}
          {activeTab === 'fixes' && (
            <div className="panel">
              <div className="panel-header">
                <div>
                  <h2 className="panel-title">Synthesized Fix Proposals</h2>
                  <div className="panel-subtitle">Automated patches targeting failed requirement tests</div>
                </div>
              </div>

              {fixSuggestions.length === 0 ? (
                <div style={{ padding: 'var(--s-6)', textAlign: 'center' }}>
                  <Sparkles size={24} style={{ color: 'var(--accent)', margin: '0 auto var(--s-2)' }} />
                  <h3 style={{ fontSize: '1.2rem', marginBottom: '4px' }}>No fixes required</h3>
                  <p style={{ color: 'var(--muted)', fontSize: 'var(--text-sm)' }}>
                    All tested requirements are currently passing or no patches were suggested.
                  </p>
                </div>
              ) : (
                <div style={{ display: 'grid', gap: 'var(--s-5)' }}>
                  {fixSuggestions.map((fix, idx) => (
                    <div key={idx} className="diff-card">
                      <div className="diff-header">
                        <span className="evidence-id-badge">Target: {fix.requirement_id}</span>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          disabled={busy}
                          onClick={() => {
                            setCode(fix.patched_code);
                            setActiveTab('retest');
                          }}
                        >
                          <Sparkles size={13} style={{ color: 'var(--accent)' }} />
                          <span>Apply to Retest Sandbox</span>
                        </button>
                      </div>

                      <div className="diff-explanation">{fix.explanation}</div>

                      <pre className="evidence-code-pre" style={{ maxHeight: '320px' }}>
                        {fix.patched_code}
                      </pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 5: RETEST SANDBOX */}
          {activeTab === 'retest' && (
            <div className="panel">
              <div className="panel-header">
                <div>
                  <h2 className="panel-title">Retest Sandbox</h2>
                  <div className="panel-subtitle">
                    Modify your Python source and re-execute the original synthesized tests
                  </div>
                </div>
              </div>

              <div style={{ marginBottom: 'var(--s-5)' }}>
                <CodeEditor
                  value={code}
                  onChange={setCode}
                  disabled={busy}
                  placeholder="# Update code to address failed requirements"
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--s-3)' }}>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--muted)' }}>
                  {busy
                    ? 'Executing saved tests against modified source…'
                    : 'Changes will be evaluated against the exact requirements already synthesized.'}
                </span>

                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={busy || !code.trim() || isNotRun}
                  onClick={retest}
                >
                  {busy ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />}
                  <span>{busy ? 'Retesting…' : 'Retest original tests'}</span>
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

import { lazy, Suspense, useEffect, useRef, useState, type ReactNode } from 'react';
import { flushSync } from 'react-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AnimatePresence, MotionConfig, motion, useReducedMotion } from 'framer-motion';
import {
  FileCheck2, FolderKanban, Gauge, Menu, Moon, Sun, Waves, PanelLeftClose, PanelLeftOpen, ShieldCheck, X
} from 'lucide-react';
import { Link, Route, Switch, useLocation, Router as WouterRouter } from 'wouter';
import { FluidInk } from '@/components/fluid-ink';
import { ErrorBoundary } from '@/components/error-boundary';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import NotFound from '@/pages/not-found';
const ConnectedDashboard = lazy(() => import('./connected').then(m => ({default: m.ConnectedDashboard})));
const ConnectedVerify = lazy(() => import('./connected').then(m => ({default: m.ConnectedVerify})));
const ConnectedListing = lazy(() => import('./connected').then(m => ({default: m.ConnectedListing})));
const ConnectedDetail = lazy(() => import('./connected').then(m => ({default: m.ConnectedDetail})));

import { AccountControls, AccountProvider, AuthGate, RequireAccount } from '@/components/account';

const queryClient = new QueryClient();

/* ───────── THEME CONTROLLER WITH CIRCULAR VIEW TRANSITION ───────── */
function useTheme() {
  const [theme, setThemeState] = useState<'dark' | 'light'>(() => {
    try {
      return localStorage.getItem('theme') === 'light' ? 'light' : 'dark';
    } catch {
      return 'dark';
    }
  });

  const reduceMotion = useReducedMotion() ?? false;

  const toggleTheme = (e?: React.MouseEvent) => {
    const nextTheme = theme === 'light' ? 'dark' : 'light';
    const root = document.documentElement;

    const applyTheme = () => {
      flushSync(() => setThemeState(nextTheme));
      root.dataset.theme = nextTheme;
      try {
        localStorage.setItem('theme', nextTheme);
      } catch {}
    };

    if (!document.startViewTransition || reduceMotion || !e) {
      applyTheme();
      return;
    }

    const x = e.clientX || window.innerWidth - 40;
    const y = e.clientY || 40;
    const endRadius = Math.hypot(
      Math.max(x, window.innerWidth - x),
      Math.max(y, window.innerHeight - y)
    );

    const transition = document.startViewTransition(() => {
      applyTheme();
    });

    transition.ready.then(() => {
      root.animate(
        {
          clipPath: [
            `circle(0px at ${x}px ${y}px)`,
            `circle(${endRadius}px at ${x}px ${y}px)`,
          ],
        },
        {
          duration: 650,
          easing: 'cubic-bezier(0.25, 1, 0.5, 1)',
          pseudoElement: '::view-transition-new(root)',
        }
      );
    });
  };

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  return { theme, toggleTheme };
}

/* ───────── BRAND MARK ───────── */
function Brand() {
  return (
    <Link href="/" className="brand-badge" aria-label="SpecGuard workbench" data-testid="link-brand">
      <div className="brand-icon-box">
        <ShieldCheck size={19} strokeWidth={2.2} />
      </div>
      <div className="brand-title">
        <span className="brand-title-name">
          Spec<span>Guard</span>
        </span>
        <span className="brand-title-sub">VERIFICATION BENCH</span>
      </div>
    </Link>
  );
}

/* ───────── NAV LINK ───────── */
function NavLink({
  href,
  icon: Icon,
  children,
  active,
  onClick,
}: {
  href: string;
  icon: typeof Gauge;
  children: ReactNode;
  active: boolean;
  onClick?: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className={`nav-item ${active ? 'active' : ''}`}
      aria-label={typeof children === 'string' ? children : undefined}
      title={typeof children === 'string' ? children : undefined}
      aria-current={active ? 'page' : undefined}
    >
      <Icon size={17} strokeWidth={1.9} style={{ color: active ? 'var(--nav-active-icon,var(--accent))' : 'inherit' }} />
      <span>{children}</span>
      {active && <motion.span className="nav-highlight" layoutId="sidebar-selection" transition={{ duration: .42, ease: [.16, 1, .3, 1] }} aria-hidden="true" />}
    </Link>
  );
}

/* ───────── APP SHELL ───────── */
function Shell({
  children,
  theme,
  toggleTheme,
}: {
  children: ReactNode;
  theme: 'dark' | 'light';
  toggleTheme: (e?: React.MouseEvent) => void;
}) {
  const [location, navigate] = useLocation();
  const curtainRef = useRef<HTMLDivElement>(null);
  const pendingRoute = useRef<string | null>(null);
  const transitionRunning = useRef(false);
  const [routeLabel, setRouteLabel] = useState('Workspace');
  const [menuOpen, setMenuOpen] = useState(false);
  const [fluidEnabled, setFluidEnabled] = useState(() => {
    try { return localStorage.getItem('specguard-fluid') === 'on'; } catch { return false; }
  });
  const toggleFluid = () => setFluidEnabled(current => {
    const enabled = !current;
    try { localStorage.setItem('specguard-fluid', enabled ? 'on' : 'off'); } catch { /* Optional preference. */ }
    return enabled;
  });
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('specguard-sidebar') === 'collapsed'; } catch { return false; }
  });
  const disturbSidebar = () => window.dispatchEvent(new CustomEvent('specguard:fluid-pulse', { detail: { x: collapsed ? 76 : 240, y: Math.min(innerHeight * .35, 300) } }));
  const toggleSidebar = () => { disturbSidebar(); setCollapsed(value => {
    try { localStorage.setItem('specguard-sidebar', value ? 'expanded' : 'collapsed'); } catch { /* Optional preference. */ }
    return !value;
  }); };
  useEffect(() => {
    setMenuOpen(false);
    window.scrollTo({ top: 0, behavior: 'instant' });
  }, [location]);
  useEffect(() => {
    if (!menuOpen) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    const navigation = document.getElementById('workspace-navigation');
    const controls = () => Array.from(navigation?.querySelectorAll<HTMLElement>('a[href],button') || []).filter(el => el.getClientRects().length > 0);
    controls()[0]?.focus();
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false);
      if (event.key !== 'Tab') return;
      const items = controls();
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener('keydown', close);
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.removeEventListener('keydown', close); document.body.style.overflow = previous; previousFocus?.focus(); };
  }, [menuOpen]);
  const reduceMotion = useReducedMotion() ?? false;
  useEffect(() => {
    const desktop = matchMedia('(min-width:1025px)');
    const releaseDrawer = () => { if (desktop.matches) setMenuOpen(false); };
    desktop.addEventListener('change', releaseDrawer);
    return () => desktop.removeEventListener('change', releaseDrawer);
  }, []);

  const runTransition = async () => {
    const curtain = curtainRef.current;
    if (!curtain || transitionRunning.current) return;
    transitionRunning.current = true;
    const target = pendingRoute.current || '/';
    setRouteLabel(target.startsWith('/verify') ? 'Verification' : target.startsWith('/projects') ? 'Projects' : target.startsWith('/reports') ? 'Reports' : 'Overview');
    setMenuOpen(false);
    let animation: Animation | undefined;
    try {
      animation = curtain.animate([{transform:'translateY(125%)'},{transform:'translateY(0)'}], {duration:420,easing:'cubic-bezier(.76,0,.24,1)',fill:'forwards'});
      await animation.finished;
      curtain.style.transform = 'translateY(0)'; animation.cancel();
      const destination = pendingRoute.current || target;
      pendingRoute.current = null;
      flushSync(() => navigate(destination));
      await new Promise<void>(resolve => requestAnimationFrame(() => resolve()));
      animation = curtain.animate([{transform:'translateY(0)'},{transform:'translateY(-125%)'}], {duration:620,easing:'cubic-bezier(.76,0,.24,1)',fill:'forwards'});
      await animation.finished;
    } catch {
      if (pendingRoute.current) { navigate(pendingRoute.current); pendingRoute.current = null; }
    } finally {
      curtain.style.transform = 'translateY(125%)'; animation?.cancel();
      transitionRunning.current = false;
      if (pendingRoute.current) void runTransition();
    }
  };
  useEffect(() => () => { curtainRef.current?.getAnimations().forEach(animation => animation.cancel()); }, []);

  const onNavigate = () => { if (menuOpen) disturbSidebar(); setMenuOpen(false); };
  const selected = (path: string) => location === path || (path !== '/' && location.startsWith(path));

  // Top scroll progress listener
  useEffect(() => {
    const onScroll = () => {
      const scrollHeight = document.documentElement.scrollHeight - window.innerHeight;
      const progress = scrollHeight > 0 ? window.scrollY / scrollHeight : 0;
      document.documentElement.style.setProperty('--scroll-p', String(progress));
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''}`} onClickCapture={event => {
      const anchor = (event.target as HTMLElement).closest<HTMLAnchorElement>('a[href]');
      if (!anchor || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || anchor.target || anchor.hasAttribute('download')) return;
      const url = new URL(anchor.href);
      const base = import.meta.env.BASE_URL.replace(/\/$/, '');
      if (url.origin !== window.location.origin || url.hash || url.pathname === window.location.pathname || (base && !url.pathname.startsWith(base + '/'))) return;
      if (reduceMotion || !curtainRef.current?.animate) return;
      event.preventDefault();
      pendingRoute.current = url.pathname.slice(base.length) + url.search;
      if (transitionRunning.current) return;
      void runTransition();
    }}>
      {fluidEnabled && <FluidInk />}
      <div className="route-curtain" ref={curtainRef} aria-hidden="true">
        <svg className="curtain-edge curtain-edge-top" viewBox="0 0 1440 180" preserveAspectRatio="none"><path d="M0 180V125C250 125 230 10 540 45S1000 180 1440 35V180Z" /></svg>
        <div className="curtain-wordmark"><ShieldCheck size={40} /><span>SpecGuard</span><span className="curtain-route">{routeLabel}</span></div>
        <svg className="curtain-edge curtain-edge-bottom" viewBox="0 0 1440 180" preserveAspectRatio="none"><path d="M0 0V55C250 55 230 170 540 135S1000 0 1440 145V0Z" /></svg>
      </div>
      <div className="scroll-progress-line" aria-hidden="true" />


      {/* Sidebar Navigation */}
      <aside id="workspace-navigation" className={`sidebar ${menuOpen ? 'mobile-open' : ''}`} aria-label="Main navigation">
        <motion.div key={`${collapsed}-${menuOpen}`} className="sidebar-sweep" aria-hidden="true" initial={reduceMotion ? false : { x: '-130%', skewX: -18 }} animate={{ x: '160%', skewX: 0 }} transition={{ duration: .85, ease: [.16, 1, .3, 1] }} />
        <div className="sidebar-header">
          <Brand />
          <button
            type="button"
            className="sidebar-close-btn"
            aria-label="Close navigation"
            onClick={onNavigate}
          >
            <X size={18} />
          </button>
        </div>

        <nav className="nav-section" aria-label="Workspace routes">
          <span className="nav-heading">WORKSPACE</span>
          <NavLink href="/" icon={Gauge} active={location === '/'} onClick={onNavigate}>
            Dashboard
          </NavLink>
          <NavLink href="/verify" icon={ShieldCheck} active={selected('/verify')} onClick={onNavigate}>
            New verification
          </NavLink>
          <NavLink href="/projects" icon={FolderKanban} active={selected('/projects')} onClick={onNavigate}>
            Projects
          </NavLink>
          <NavLink href="/reports" icon={FileCheck2} active={selected('/reports')} onClick={onNavigate}>
            Reports
          </NavLink>
        </nav>

        <div className="sidebar-spacer" />

        <div className="sidebar-footer">
          <span>
            <span className="footer-status-dot" /> SpecGuard v0.2.0
          </span>
          <span className="mono">PYTEST</span>
        </div>
      </aside>

      {/* Mobile scrim backdrop */}
      <AnimatePresence>{menuOpen && (
        <motion.div
          key="navigation-scrim"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          transition={{ duration: reduceMotion ? 0 : .35 }}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 35,
            background: 'rgba(0, 0, 0, 0.65)',
            backdropFilter: 'blur(4px)',
          }}
          onClick={onNavigate}
          aria-hidden="true"
        />
      )}</AnimatePresence>

      {/* Main Content View */}
      <main className="main-column" inert={menuOpen || undefined}>
        <header className="topbar">
          <div className="topbar-left">
            <button className="sidebar-collapse-trigger" onClick={toggleSidebar} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed} aria-controls="workspace-navigation" title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
              {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
            </button>
            <button
              type="button"
              className="mobile-menu-trigger"
              aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'}
              aria-expanded={menuOpen}
              aria-controls="workspace-navigation"
              onClick={() => { disturbSidebar(); setMenuOpen(value => !value); }}
            >
              {menuOpen ? <X size={18} /> : <Menu size={18} />}
            </button>
            <div className="topbar-crumb">
              <span>SpecGuard</span>
              <span className="crumb-separator">/</span>
              <span className="crumb-current">
                {location === '/'
                  ? 'Overview'
                  : location.startsWith('/verify')
                  ? 'Verification'
                  : location.startsWith('/projects')
                  ? 'Projects'
                  : location.startsWith('/reports')
                  ? 'Reports'
                  : location === '/login' ? 'Log in' : 'Workspace'}
              </span>
            </div>
          </div>

          <div className="topbar-right">
            <AccountControls />
            <button type="button" className="theme-toggle-btn fluid-toggle-btn" onClick={toggleFluid}
              aria-label="Fluid animations" aria-pressed={fluidEnabled}
              title={fluidEnabled ? 'Turn fluid animations off' : 'Turn fluid animations on'}>
              <Waves size={18} />
            </button>

            {/* Circular Theme Toggle Button */}
            <button
              type="button"
              className="theme-toggle-btn"
              onClick={toggleTheme}
              aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
              title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            >
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </button>

            <Link href="/verify" className="btn btn-primary btn-sm">
              <ShieldCheck size={14} />
              <span>Verify</span>
            </Link>
          </div>
        </header>

        <motion.div
          className="content-area"
          key={location}
          initial={reduceMotion ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: reduceMotion ? 0 : 0.5, ease: [0.16, 1, 0.3, 1] }}
        >
          {children}
        </motion.div>
      </main>
    </div>
  );
}

function RoutedErrorBoundary({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  return <ErrorBoundary resetKey={location}>{children}</ErrorBoundary>;
}

/* ───────── ROOT APP ───────── */
export function App() {
  const { theme, toggleTheme } = useTheme();
  return (
    <QueryClientProvider client={queryClient}>
      <MotionConfig reducedMotion="user">
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
          <AccountProvider>
          <RoutedErrorBoundary>
            <Shell theme={theme} toggleTheme={toggleTheme}>
              <Suspense fallback={<p role="status">Loading workspace…</p>}><Switch>
                <Route path="/" component={ConnectedDashboard} />
                <Route path="/login" component={AuthGate} />
                <Route path="/verify"><RequireAccount><ConnectedVerify /></RequireAccount></Route>
                <Route path="/projects"><RequireAccount><ConnectedListing kind="projects" /></RequireAccount></Route>
                <Route path="/projects/:projectId">
                  {(params) => <RequireAccount><ConnectedDetail kind="project" id={params.projectId} /></RequireAccount>}
                </Route>
                <Route path="/reports"><RequireAccount><ConnectedListing kind="reports" /></RequireAccount></Route>
                <Route path="/reports/:projectId">
                  {(params) => <RequireAccount><ConnectedDetail kind="report" id={params.projectId} /></RequireAccount>}
                </Route>
                <Route component={NotFound} />
              </Switch></Suspense>
            </Shell>
          </RoutedErrorBoundary>
          </AccountProvider>
        </WouterRouter>
        <Toaster />
      </TooltipProvider>
      </MotionConfig>
    </QueryClientProvider>
  );
}

export default App;

import { ReactNode, useEffect, useState } from 'react';
import AgentSessionsDashboard from './components/AgentSessionsDashboard';
import DashboardPage from './components/DashboardPage';
import CurrentStateMapsPage from './components/CurrentStateMapsPage';
import FormsPage from './components/FormsPage';
import ReviewQueuePanel from './components/ReviewQueuePanel';
import SettingsPage from './components/SettingsPage';
import WorkflowCanvasPanel from './components/WorkflowCanvasPanel';
import { AuthControls } from './auth';
import { PortalRoute, parseRoute, routePath } from './dashboardModel';
import './App.css';

// Legacy coding-agent dashboard stays in the codebase but out of the product UI.
const agentDashboardEnabled = import.meta.env.VITE_ENABLE_AGENT_DASHBOARD === 'true';

type NavItem = { route: PortalRoute; label: string; icon: ReactNode };
type NavSection = { title?: string; items: NavItem[] };

const ICONS: Record<PortalRoute, ReactNode> = {
  dashboard: (
    <svg fill="none" strokeWidth={2} viewBox="0 0 24 24">
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </svg>
  ),
  forms: (
    <svg fill="none" strokeWidth={2} viewBox="0 0 24 24">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6M9 13h6M9 17h6" />
    </svg>
  ),
  'process-maps': (
    <svg fill="none" strokeWidth={2} viewBox="0 0 24 24">
      <rect x="3" y="4" width="7" height="6" rx="1.5" />
      <rect x="14" y="14" width="7" height="6" rx="1.5" />
      <path d="M6.5 10v3a2 2 0 0 0 2 2H14" />
    </svg>
  ),
  workflows: (
    <svg fill="none" strokeWidth={2} viewBox="0 0 24 24">
      <circle cx="5" cy="6" r="2.5" />
      <circle cx="19" cy="18" r="2.5" />
      <path d="M7.5 6H15a3 3 0 0 1 3 3v6.5" />
    </svg>
  ),
  review: (
    <svg fill="none" strokeWidth={2} viewBox="0 0 24 24">
      <path d="M22 11.1V12a10 10 0 1 1-5.93-9.14" />
      <path d="M22 4 12 14l-3-3" />
    </svg>
  ),
  clients: (
    <svg fill="none" strokeWidth={2} viewBox="0 0 24 24">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
  settings: (
    <svg fill="none" strokeWidth={2} viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
};

const NAV_SECTIONS: NavSection[] = [
  {
    items: [
      { route: 'dashboard', label: 'Dashboard', icon: ICONS.dashboard },
      { route: 'forms', label: 'Forms', icon: ICONS.forms },
      { route: 'process-maps', label: 'Current state', icon: ICONS['process-maps'] },
      { route: 'workflows', label: 'Workflows', icon: ICONS.workflows },
      { route: 'review', label: 'Review queue', icon: ICONS.review },
      { route: 'clients', label: 'Clients', icon: ICONS.clients },
    ],
  },
  {
    title: 'Account',
    items: [{ route: 'settings', label: 'Settings', icon: ICONS.settings }],
  },
];

function ComingSoonPage({ title, blurb }: { title: string; blurb: string }) {
  return (
    <div className="sts-coming-soon">
      <h2>{title}</h2>
      <p>{blurb}</p>
      <span className="sts-coming-soon-badge">Coming soon</span>
    </div>
  );
}

export default function App() {
  const [route, setRoute] = useState<PortalRoute>(() => parseRoute(window.location.pathname));

  useEffect(() => {
    const onPopState = () => setRoute(parseRoute(window.location.pathname));
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  function navigate(next: PortalRoute) {
    window.history.pushState(null, '', routePath(next));
    setRoute(next);
  }

  function navigateToPath(path: string) {
    window.history.pushState(null, '', path);
    setRoute(parseRoute(path));
  }

  // The canvas takes over the whole viewport; the engine's own sidebar logo
  // navigates back to the STS dashboard once the user is at its home page.
  if (route === 'workflows') {
    return <WorkflowCanvasPanel fullScreen />;
  }

  return (
    <div className="sts-layout">
      <aside className="sts-sidebar">
        <button type="button" className="sts-logo" onClick={() => navigate('dashboard')} aria-label="Simple Technology Solutions dashboard">
          <img
            className="sts-sidebar-logo"
            src="/brand/sts-logo-secondary.png"
            alt="Simple Technology Solutions"
            width="112"
            height="108"
          />
        </button>
        <nav className="sts-nav" aria-label="Portal">
          {NAV_SECTIONS.map((section, index) => (
            <div key={section.title ?? `section-${index}`}>
              {section.title ? <div className="sts-nav-section">{section.title}</div> : null}
              {section.items.map((item) => (
                <button
                  key={item.route}
                  type="button"
                  className={route === item.route ? 'sts-nav-link sts-nav-active' : 'sts-nav-link'}
                  onClick={() => navigate(item.route)}
                  aria-current={route === item.route ? 'page' : undefined}
                >
                  {item.icon}
                  {item.label}
                </button>
              ))}
            </div>
          ))}
        </nav>
        <div className="sts-sidebar-footer">
          <AuthControls />
        </div>
      </aside>

      <main className="sts-main">
        {route === 'dashboard' ? <DashboardPage onNavigate={navigate} /> : null}
        {route === 'forms' ? <FormsPage /> : null}
        {route === 'review' ? <ReviewQueuePanel /> : null}
        {route === 'process-maps' ? <CurrentStateMapsPage onNavigate={navigateToPath} /> : null}
        {route === 'clients' ? (
          <ComingSoonPage
            title="Clients"
            blurb="A directory of your active clients and their intake activity will live here."
          />
        ) : null}
        {route === 'settings' ? <SettingsPage /> : null}
        {agentDashboardEnabled ? <AgentSessionsDashboard /> : null}
      </main>
    </div>
  );
}

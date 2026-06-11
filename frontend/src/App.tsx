import { useEffect, useState } from 'react';
import AgentSessionsDashboard from './components/AgentSessionsDashboard';
import DashboardPage from './components/DashboardPage';
import FormsPage from './components/FormsPage';
import ReviewQueuePanel from './components/ReviewQueuePanel';
import WorkflowCanvasPanel from './components/WorkflowCanvasPanel';
import { AuthControls } from './auth';
import { PortalRoute, parseRoute, routePath } from './dashboardModel';
import './App.css';

// Legacy coding-agent dashboard stays in the codebase but out of the product UI.
const agentDashboardEnabled = import.meta.env.VITE_ENABLE_AGENT_DASHBOARD === 'true';

const NAV_ITEMS: { route: PortalRoute; label: string }[] = [
  { route: 'dashboard', label: 'Dashboard' },
  { route: 'forms', label: 'Forms' },
  { route: 'workflows', label: 'Workflows' },
  { route: 'review', label: 'Review queue' },
];

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

  // The canvas takes over the whole viewport; the engine's own sidebar logo
  // navigates back to the STS dashboard once the user is at its home page.
  if (route === 'workflows') {
    return <WorkflowCanvasPanel fullScreen />;
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <h1>SimpleTS</h1>
          <p>Submit once → review once → distribute everywhere.</p>
        </div>
        <AuthControls />
      </header>
      <nav className="portal-nav" aria-label="Portal">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.route}
            type="button"
            className={route === item.route ? 'portal-nav-active' : undefined}
            onClick={() => navigate(item.route)}
            aria-current={route === item.route ? 'page' : undefined}
          >
            {item.label}
          </button>
        ))}
      </nav>
      {route === 'dashboard' ? <DashboardPage onNavigate={navigate} /> : null}
      {route === 'forms' ? <FormsPage /> : null}
      {route === 'review' ? <ReviewQueuePanel /> : null}
      {agentDashboardEnabled ? <AgentSessionsDashboard /> : null}
    </main>
  );
}

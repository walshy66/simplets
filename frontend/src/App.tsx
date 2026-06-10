import { useEffect, useState } from 'react';
import { listSessions, restartSession, resumeSession, Session, startSession, stopSession } from './api';
import DocumentUploadPanel from './components/DocumentUploadPanel';
import ReviewQueuePanel from './components/ReviewQueuePanel';
import SessionCreateForm from './components/SessionCreateForm';
import { AuthControls } from './auth';
import { resolveSelectedSession } from './sessionSelectionModel';
import SessionDetail from './components/SessionDetail';
import SessionList from './components/SessionList';
import './App.css';

const SELECTED_SESSION_STORAGE_KEY = 'simplets.selectedSessionId';

function getStoredSelectedSessionId(): string | null {
  return window.localStorage.getItem(SELECTED_SESSION_STORAGE_KEY);
}

export default function App() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(() => getStoredSelectedSessionId());
  const [selected, setSelected] = useState<Session | null>(null);

  async function refreshSessions() {
    const nextSessions = await listSessions();
    setSessions(nextSessions);
    setSelected(resolveSelectedSession(nextSessions, selectedId));
  }

  useEffect(() => {
    refreshSessions();
  }, []);

  useEffect(() => {
    if (selectedId) {
      window.localStorage.setItem(SELECTED_SESSION_STORAGE_KEY, selectedId);
    } else {
      window.localStorage.removeItem(SELECTED_SESSION_STORAGE_KEY);
    }
  }, [selectedId]);

  function handleSessionSelected(session: Session) {
    setSelectedId(session.id);
    setSelected(session);
  }

  function handleSessionChanged(session: Session) {
    setSelectedId(session.id);
    setSelected(session);
    setSessions((current) => current.map((item) => (item.id === session.id ? session : item)));
  }

  function handleSessionCreated(session: Session) {
    setSessions((current) => [session, ...current]);
    setSelectedId(session.id);
    setSelected(session);
  }

  async function handleSessionStart(session: Session) {
    handleSessionChanged(await startSession(session.id));
  }

  async function handleSessionStop(session: Session) {
    handleSessionChanged(await stopSession(session.id));
  }

  async function handleSessionResume(session: Session) {
    handleSessionChanged(await resumeSession(session.id));
  }

  async function handleSessionRestart(session: Session) {
    handleSessionChanged(await restartSession(session.id));
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <h1>SimpleTS</h1>
          <p>Local laptop MVP for managing coding-agent sessions.</p>
        </div>
        <AuthControls />
      </header>
      <div className="session-dashboard">
        <div className="session-sidebar">
          <DocumentUploadPanel />
          <ReviewQueuePanel />
          <SessionCreateForm onCreated={handleSessionCreated} />
          <SessionList
            sessions={sessions}
            selectedId={selected?.id || null}
            onSelect={handleSessionSelected}
            onStart={handleSessionStart}
            onStop={handleSessionStop}
            onResume={handleSessionResume}
            onRestart={handleSessionRestart}
          />
        </div>
        <SessionDetail session={selected} onChanged={handleSessionChanged} />
      </div>
    </main>
  );
}

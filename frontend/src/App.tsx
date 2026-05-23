import { useEffect, useState } from 'react';
import { listSessions, Session } from './api';
import SessionCreateForm from './components/SessionCreateForm';
import SessionDetail from './components/SessionDetail';
import SessionList from './components/SessionList';

export default function App() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selected, setSelected] = useState<Session | null>(null);

  async function refreshSessions() {
    const nextSessions = await listSessions();
    setSessions(nextSessions);
    if (selected) {
      const updatedSelected = nextSessions.find((session) => session.id === selected.id) || null;
      setSelected(updatedSelected);
    }
  }

  useEffect(() => {
    refreshSessions();
  }, []);

  function handleSessionChanged(session: Session) {
    setSelected(session);
    setSessions((current) => current.map((item) => (item.id === session.id ? session : item)));
  }

  function handleSessionCreated(session: Session) {
    setSessions((current) => [session, ...current]);
    setSelected(session);
  }

  return (
    <main style={{ fontFamily: 'Arial, sans-serif', padding: 24 }}>
      <header style={{ marginBottom: 24 }}>
        <h1>SimpleTS</h1>
        <p>Local laptop MVP for managing coding-agent sessions.</p>
      </header>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 1fr) minmax(360px, 2fr)', gap: 16 }}>
        <div style={{ display: 'grid', gap: 16 }}>
          <SessionCreateForm onCreated={handleSessionCreated} />
          <SessionList sessions={sessions} selectedId={selected?.id || null} onSelect={setSelected} />
        </div>
        <SessionDetail session={selected} onChanged={handleSessionChanged} />
      </div>
    </main>
  );
}

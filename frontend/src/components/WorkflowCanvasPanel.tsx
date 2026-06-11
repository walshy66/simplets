import { useEffect, useState } from 'react';
import { getWorkflowCanvas } from '../api';

/** Embedded workflow canvas (COA-284). The embed URL is issued by the backend
 * only to authenticated workspace admins. `stsHome` tells the embedded engine
 * where its sidebar logo should return to once the user is at its home page. */
function useCanvasEmbedUrl() {
  const [embedUrl, setEmbedUrl] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getWorkflowCanvas()
      .then((canvas) => {
        if (!cancelled) {
          const url = new URL(canvas.embed_url);
          url.searchParams.set('stsHome', `${window.location.origin}/`);
          setEmbedUrl(url.toString());
        }
      })
      .catch(() => {
        if (!cancelled) {
          setUnavailable(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { embedUrl, unavailable };
}

const UNAVAILABLE_NOTICE =
  'Workflow canvas is not available — it may not be configured yet, or your role does not include workflow management.';

export default function WorkflowCanvasPanel({ fullScreen = false }: { fullScreen?: boolean }) {
  const { embedUrl, unavailable } = useCanvasEmbedUrl();

  if (fullScreen) {
    if (unavailable) {
      return (
        <section className="panel workflow-canvas-panel" aria-labelledby="workflow-canvas-title">
          <h2 id="workflow-canvas-title">Workflows</h2>
          <p>{UNAVAILABLE_NOTICE}</p>
          <a href="/">← Back to dashboard</a>
        </section>
      );
    }
    if (!embedUrl) {
      return null;
    }
    return (
      <div className="workflow-canvas-fullscreen">
        <iframe src={embedUrl} title="Workflow canvas" />
      </div>
    );
  }

  if (unavailable) {
    return (
      <section className="panel workflow-canvas-panel" aria-labelledby="workflow-canvas-title">
        <h2 id="workflow-canvas-title">Workflow canvas</h2>
        <p>{UNAVAILABLE_NOTICE}</p>
      </section>
    );
  }

  if (!embedUrl) {
    return null;
  }

  return (
    <section className="panel workflow-canvas-panel" aria-labelledby="workflow-canvas-title">
      <h2 id="workflow-canvas-title">Workflow canvas</h2>
      <iframe className="workflow-canvas-frame" src={embedUrl} title="Workflow canvas" />
    </section>
  );
}

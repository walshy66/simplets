import { useEffect, useState } from 'react';
import { Workspace, getCurrentWorkspace, updateWorkspaceBranding, uploadWorkspaceLogo } from '../api';
import {
  Theme,
  applyTheme,
  persistTheme,
  readStoredTheme,
  resolveInitialTheme,
  systemPrefersDark,
} from '../theme';
import BrandLogo from './BrandLogo';

export default function SettingsPage() {
  const [theme, setTheme] = useState<Theme>(() =>
    resolveInitialTheme(readStoredTheme(), systemPrefersDark()),
  );
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [logoUrl, setLogoUrl] = useState('');
  const [savingLogo, setSavingLogo] = useState(false);
  const [logoStatus, setLogoStatus] = useState<string | null>(null);
  const [selectedLogoFile, setSelectedLogoFile] = useState<File | null>(null);

  function uploadLogo(file: File | null) {
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setLogoStatus('Choose an image file for the workspace logo.');
      return;
    }

    setSelectedLogoFile(file);
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        setLogoUrl(reader.result);
        setLogoStatus('Logo uploaded for preview. Save to apply it to this workspace.');
      }
    };
    reader.onerror = () => setLogoStatus('Could not read logo image.');
    reader.readAsDataURL(file);
  }

  async function useReGroupDemoLogo() {
    setLogoStatus(null);
    try {
      const response = await fetch('/brand/regroup-logo.png');
      if (!response.ok) throw new Error('logo not found');
      const blob = await response.blob();
      uploadLogo(new File([blob], 'regrouplogo.png', { type: blob.type || 'image/png' }));
    } catch {
      setLogoStatus('Could not load the ReGroup demo logo.');
    }
  }

  useEffect(() => {
    let cancelled = false;
    getCurrentWorkspace()
      .then((ws) => {
        if (cancelled) return;
        setWorkspace(ws);
        setLogoUrl(ws.branding_logo_url ?? '');
      })
      .catch(() => {
        /* leave defaults; branding section still renders the STS platform fallback */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function choose(next: Theme) {
    setTheme(next);
    applyTheme(next);
    persistTheme(next);
  }

  async function saveLogo() {
    setSavingLogo(true);
    setLogoStatus(null);
    try {
      let ws: Workspace;
      if (selectedLogoFile) {
        ws = await uploadWorkspaceLogo(selectedLogoFile);
      } else {
        const trimmed = logoUrl.trim();
        ws = await updateWorkspaceBranding({
          logo_url: trimmed || null,
          primary_color: workspace?.branding_primary_color ?? null,
        });
      }
      setWorkspace(ws);
      setLogoUrl(ws.branding_logo_url ?? '');
      setSelectedLogoFile(null);
      setLogoStatus(
        ws.branding_logo_url ? 'Logo saved.' : 'Logo cleared — showing the STS platform default.',
      );
    } catch {
      setLogoStatus('Could not save branding. Logo uploads must be PNG, JPEG, WebP, or SVG files under 2 MB.');
    } finally {
      setSavingLogo(false);
    }
  }

  return (
    <div className="settings-page">
      <header className="settings-head">
        <h2>Settings</h2>
        <p>Manage your SimpleTS workspace appearance.</p>
      </header>

      <section className="panel settings-section" aria-labelledby="settings-appearance">
        <h3 id="settings-appearance">Appearance</h3>
        <div className="settings-row">
          <div className="settings-row-label">
            <strong>Theme</strong>
            <p className="settings-hint">Switch between light and dark.</p>
          </div>
          <div className="settings-segment" role="group" aria-label="Theme">
            <button
              type="button"
              className={theme === 'light' ? 'is-active' : undefined}
              aria-pressed={theme === 'light'}
              onClick={() => choose('light')}
            >
              Light
            </button>
            <button
              type="button"
              className={theme === 'dark' ? 'is-active' : undefined}
              aria-pressed={theme === 'dark'}
              onClick={() => choose('dark')}
            >
              Dark
            </button>
          </div>
        </div>
      </section>

      <section className="panel settings-section" aria-labelledby="settings-branding">
        <h3 id="settings-branding">Branding</h3>
        <div className="settings-row">
          <div className="settings-row-label">
            <strong>Workspace logo</strong>
            <p className="settings-hint">
              Shown on your dashboard. Upload an image or paste an image URL; leave blank to use the Simple Technology Solutions default.
            </p>
          </div>
          <div className="settings-logo-preview" aria-label="Logo preview">
            <BrandLogo logoUrl={logoUrl.trim() || null} name={workspace?.name} />
          </div>
        </div>
        <label htmlFor="branding-logo-file">Upload logo image</label>
        <input
          id="branding-logo-file"
          className="form-control"
          type="file"
          accept="image/*"
          onChange={(event) => uploadLogo(event.target.files?.[0] ?? null)}
        />
        <button type="button" className="settings-secondary-action" onClick={useReGroupDemoLogo}>
          Use ReGroup demo logo
        </button>
        <label htmlFor="branding-logo-url">Logo URL or uploaded image data</label>
        <input
          id="branding-logo-url"
          className="form-control"
          type="text"
          placeholder="https://example.com/logo.png"
          value={logoUrl}
          onChange={(event) => setLogoUrl(event.target.value)}
        />
        <div className="settings-actions">
          <button type="button" onClick={saveLogo} disabled={savingLogo}>
            {savingLogo ? 'Saving…' : 'Save logo'}
          </button>
          {logoStatus ? <span className="settings-hint">{logoStatus}</span> : null}
        </div>
      </section>
    </div>
  );
}

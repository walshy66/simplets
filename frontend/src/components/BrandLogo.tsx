import { useEffect, useState } from 'react';

/**
 * White-label brand slot shown in tenant contexts. Renders the subscriber's
 * configured logo when set; otherwise falls back to the Simple Technology
 * Solutions platform lockup. Also falls back if the configured image fails to
 * load.
 */
export default function BrandLogo({ logoUrl, name }: { logoUrl: string | null; name?: string }) {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [logoUrl]);

  if (logoUrl && !failed) {
    const src = logoUrl.startsWith('/workspace-branding/') ? `http://localhost:8000${logoUrl}` : logoUrl;
    return (
      <img
        className="brand-logo-img"
        src={src}
        alt={name ? `${name} logo` : 'Workspace logo'}
        onError={() => setFailed(true)}
      />
    );
  }

  return (
    <img
      className="brand-logo-default"
      src="/brand/sts-wordmark-white.png"
      alt="Simple Technology Solutions"
      width="190"
      height="138"
    />
  );
}

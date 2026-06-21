import { useId } from 'react';

type STSLogoVariant = 'full' | 'mark';

type STSLogoProps = {
  variant?: STSLogoVariant;
  className?: string;
  title?: string;
};

/**
 * Scalable Simple Technology Solutions platform mark.
 *
 * The product remains SimpleTS, but this platform chrome uses the STS corporate
 * identity from the brand kit. Workspace/client logos should override this only
 * in tenant-branded contexts.
 */
export default function STSLogo({
  variant = 'full',
  className,
  title = 'Simple Technology Solutions',
}: STSLogoProps) {
  const titleId = useId();
  const labelledBy = title ? titleId : undefined;

  if (variant === 'mark') {
    return (
      <svg
        className={className ? `sts-brand-mark ${className}` : 'sts-brand-mark'}
        viewBox="0 0 104 52"
        role="img"
        aria-labelledby={labelledBy}
        focusable="false"
      >
        {title ? <title id={titleId}>{title}</title> : null}
        <text x="0" y="42" className="sts-brand-letter sts-brand-letter-teal">
          S
        </text>
        <text x="34" y="42" className="sts-brand-letter sts-brand-letter-mint">
          T
        </text>
        <text x="69" y="42" className="sts-brand-letter sts-brand-letter-teal">
          S
        </text>
      </svg>
    );
  }

  return (
    <svg
      className={className ? `sts-brand-lockup ${className}` : 'sts-brand-lockup'}
      viewBox="0 0 420 106"
      role="img"
      aria-labelledby={labelledBy}
      focusable="false"
    >
      {title ? <title id={titleId}>{title}</title> : null}
      <text x="120" y="48" textAnchor="middle" className="sts-brand-letter sts-brand-letter-teal">
        S
      </text>
      <text x="166" y="48" textAnchor="middle" className="sts-brand-letter sts-brand-letter-mint">
        T
      </text>
      <text x="212" y="48" textAnchor="middle" className="sts-brand-letter sts-brand-letter-teal">
        S
      </text>
      <text x="210" y="88" textAnchor="middle" className="sts-brand-wordmark">
        Simple Technology Solutions
      </text>
    </svg>
  );
}

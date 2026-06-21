import { useEffect, useMemo, useState } from 'react';
import { ReviewQueueItem, Workspace, getCurrentWorkspace, listReviewQueue } from '../api';
import { useDevAuth } from '../auth';
import BrandLogo from './BrandLogo';
import ReviewQueueRow, { reviewItemKind, reviewItemTitle } from './ReviewQueueRow';
import {
  DUMMY_AI_USAGE,
  DUMMY_CLIENT_COUNT,
  DUMMY_WORKFLOW_COUNT,
  PORTAL_FORMS,
  PortalRoute,
  formatRenewalDate,
  greeting,
  liveFormCount,
  relativeTime,
  usagePercent,
  usageRemaining,
  usageRenewalDate,
} from '../dashboardModel';

type ReviewFilter = 'all' | 'pending' | 'approved';

const FILTERS: { id: ReviewFilter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'pending', label: 'Pending' },
  { id: 'approved', label: 'Approved' },
];

export default function DashboardPage({ onNavigate }: { onNavigate: (route: PortalRoute) => void }) {
  const [queue, setQueue] = useState<ReviewQueueItem[] | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [filter, setFilter] = useState<ReviewFilter>('all');
  const devAuth = useDevAuth();

  useEffect(() => {
    let cancelled = false;
    listReviewQueue()
      .then((items) => {
        if (!cancelled) setQueue(items);
      })
      .catch(() => {
        if (!cancelled) setQueue(null);
      });
    getCurrentWorkspace()
      .then((ws) => {
        if (!cancelled) setWorkspace(ws);
      })
      .catch(() => {
        if (!cancelled) setWorkspace(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const usage = DUMMY_AI_USAGE;
  const percent = usagePercent(usage);
  const renewal = formatRenewalDate(usageRenewalDate(new Date()));

  // The endpoint only returns pending runs today, so approved is always empty.
  const pending = queue ?? [];
  const pendingCount = queue === null ? null : pending.length;
  const actionItems = pending.slice(0, 2);

  const name = devAuth?.userId ? devAuth.userId.split(/[\s_\-.]+/)[0] : null;
  const heading = name ? `${greeting()}, ${name}` : greeting();

  const filtered = useMemo(() => {
    if (filter === 'approved') return [];
    return pending;
  }, [filter, pending]);

  return (
    <div className="dash">
      <section className="dash-hero">
        <div className="dash-hero-main">
          <span className="dash-hero-kicker">Make Work Simple</span>
          <h1>{heading}</h1>
          <p className="dash-hero-sub">
            {pendingCount === null
              ? 'Loading your review queue…'
              : pendingCount === 0
                ? "You're all caught up — nothing waiting for review."
                : `${pendingCount} item${pendingCount === 1 ? '' : 's'} waiting for your review`}
          </p>
          {actionItems.length > 0 ? (
            <div className="dash-actions">
              {actionItems.map((item) => (
                <div className="dash-action" key={item.id}>
                  <span className="dash-dot" />
                  <span className="dash-action-title">
                    {reviewItemTitle(item)} — {reviewItemKind(item)}
                  </span>
                  <span className="dash-action-when">{relativeTime(new Date(item.created_at))}</span>
                  <button type="button" className="dash-btn-mint" onClick={() => onNavigate('review')}>
                    Review
                  </button>
                </div>
              ))}
            </div>
          ) : null}
        </div>
        <div className="dash-hero-art">
          <BrandLogo logoUrl={workspace?.branding_logo_url ?? null} name={workspace?.name} />
        </div>
      </section>

      <div className="dash-row">
        <div className="dash-tiles">
          <div className="dash-tile dash-tile-usage">
            <div className="dash-tile-top">
              <span className="dash-tile-icon ti-mint">
                <svg fill="none" strokeWidth={2.2} viewBox="0 0 24 24">
                  <path d="M13 2 3 14h9l-1 8 10-12h-9z" />
                </svg>
              </span>
              <h3>Usage</h3>
            </div>
            <div className="dash-n">{percent}%</div>
            <div
              className="dash-mini-bar"
              role="progressbar"
              aria-valuenow={percent}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Execution usage"
            >
              <div className="dash-mini-fill" style={{ width: `${percent}%` }} />
            </div>
            <div className="dash-usage-row">
              <span>
                {usage.used.toLocaleString()} of {usage.limit.toLocaleString()} units
              </span>
              <span>{usageRemaining(usage).toLocaleString()} left · renews {renewal}</span>
            </div>
          </div>

          <button type="button" className="dash-tile" onClick={() => onNavigate('forms')}>
            <div className="dash-tile-top">
              <span className="dash-tile-icon ti-cyan">
                <svg fill="none" strokeWidth={2.2} viewBox="0 0 24 24">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <path d="M14 2v6h6" />
                </svg>
              </span>
              <h3>Forms</h3>
            </div>
            <div className="dash-n">{liveFormCount(PORTAL_FORMS)}</div>
            <small>live intake form{liveFormCount(PORTAL_FORMS) === 1 ? '' : 's'}</small>
          </button>

          <button type="button" className="dash-tile" onClick={() => onNavigate('workflows')}>
            <div className="dash-tile-top">
              <span className="dash-tile-icon ti-navy">
                <svg fill="none" strokeWidth={2.2} viewBox="0 0 24 24">
                  <circle cx="5" cy="6" r="2.5" />
                  <circle cx="19" cy="18" r="2.5" />
                  <path d="M7.5 6H15a3 3 0 0 1 3 3v6.5" />
                </svg>
              </span>
              <h3>Workflows</h3>
            </div>
            <div className="dash-n">{DUMMY_WORKFLOW_COUNT}</div>
            <small>moving your client data</small>
          </button>

          <button type="button" className="dash-tile" onClick={() => onNavigate('review')}>
            <div className="dash-tile-top">
              <span className="dash-tile-icon ti-amber">
                <svg fill="none" strokeWidth={2.2} viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M12 6v6l4 2" />
                </svg>
              </span>
              <h3>Review queue</h3>
            </div>
            <div className="dash-n">{pendingCount ?? '—'}</div>
            <small>waiting for review</small>
          </button>

          <button type="button" className="dash-tile" onClick={() => onNavigate('clients')}>
            <div className="dash-tile-top">
              <span className="dash-tile-icon ti-cyan">
                <svg fill="none" strokeWidth={2.2} viewBox="0 0 24 24">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                </svg>
              </span>
              <h3>Clients</h3>
            </div>
            <div className="dash-n">{DUMMY_CLIENT_COUNT}</div>
            <small>active clients</small>
          </button>
        </div>

        <div className="dash-panel">
          <div className="dash-panel-head">
            <h2>Review queue</h2>
            <div className="dash-filters">
              {FILTERS.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  className={filter === option.id ? 'dash-filter dash-filter-on' : 'dash-filter'}
                  onClick={() => setFilter(option.id)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
          {filtered.length === 0 ? (
            <p className="dash-empty">
              {filter === 'approved'
                ? 'Approved runs are not shown here yet.'
                : pendingCount === null
                  ? 'Loading…'
                  : 'Nothing waiting for review.'}
            </p>
          ) : (
            filtered.map((item) => (
              <ReviewQueueRow key={item.id} item={item} onReview={() => onNavigate('review')} />
            ))
          )}
        </div>
      </div>
    </div>
  );
}

import { ReviewQueueItem } from '../api';
import { initials, relativeTime } from '../dashboardModel';

// Form submissions land with a generic filename; the submitter name (stored as
// the document uploader) is the client/business label worth surfacing.
export function reviewItemTitle(item: ReviewQueueItem): string {
  return item.document.uploader || item.document.filename;
}

export function reviewItemKind(item: ReviewQueueItem): string {
  return item.suggested_classification || item.intent;
}

/**
 * One review-queue row, shared by the dashboard panel and the full Review page
 * so both present submissions identically (avatar · client name · kind · time).
 */
export default function ReviewQueueRow({
  item,
  onReview,
  selected = false,
}: {
  item: ReviewQueueItem;
  onReview: (id: string) => void;
  selected?: boolean;
}) {
  const title = reviewItemTitle(item);
  return (
    <div className={selected ? 'dash-qrow dash-qrow-selected' : 'dash-qrow'}>
      <span className="dash-qavatar">{initials(title)}</span>
      <div className="dash-qbody">
        <div className="dash-qtitle">{title}</div>
        <div className="dash-qmeta">
          {reviewItemKind(item)} · {relativeTime(new Date(item.created_at))}
        </div>
      </div>
      <span className="dash-tag dash-tag-pending">Pending</span>
      <button type="button" className="dash-btn-sm" onClick={() => onReview(item.id)}>
        Review
      </button>
    </div>
  );
}

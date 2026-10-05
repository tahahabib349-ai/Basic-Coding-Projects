import { useState, type ReactNode } from 'react';
import { CircleAlert, CircleCheck, Info, LoaderCircle, X } from 'lucide-react';
import { isUnknown, NEEDS_INPUT, type Recommendation, type Status } from '../lib/core';
import { useWorkspace } from '../state';

/** The signature mark: an unresolved fact, bracketed and highlighted the way open points are in a draft term sheet. */
export function OpenTerm({ children = NEEDS_INPUT }: { children?: ReactNode }) {
  return (
    <span className="open-term">
      <span className="open-term-dot" aria-hidden="true">
        [●]
      </span>{' '}
      {children}
    </span>
  );
}

/** Shows the value, or an open term when the fact is unknown. */
export function Fact({ value, open = NEEDS_INPUT }: { value?: string | null; open?: string }) {
  return isUnknown(value) ? <OpenTerm>{open}</OpenTerm> : <>{value}</>;
}

export function Terms({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <dl className={`terms ${className}`}>{children}</dl>;
}

export function Term({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <div className="term">
      <dt>
        {label}
        {hint && <span className="term-hint">{hint}</span>}
      </dt>
      <dd>{children}</dd>
    </div>
  );
}

const recTone: Record<Recommendation, string> = {
  'STRONG APPLY': 'strong',
  APPLY: 'apply',
  BORDERLINE: 'borderline',
  'LOW PRIORITY': 'low',
  'NOT SUITABLE': 'unsuitable',
};
const recLabel: Record<Recommendation, string> = {
  'STRONG APPLY': 'Strong apply',
  APPLY: 'Apply',
  BORDERLINE: 'Borderline',
  'LOW PRIORITY': 'Low priority',
  'NOT SUITABLE': 'Not suitable',
};
export const recommendationLabel = (r: Recommendation) => recLabel[r];

export function RecTag({ value, estimate }: { value?: Recommendation; estimate?: boolean }) {
  if (!value) return <span className="rec rec-none">{estimate ? 'Quick estimate' : 'Not analysed'}</span>;
  return <span className={`rec rec-${recTone[value]}`}>{recLabel[value]}</span>;
}

export function scoreTone(score?: number) {
  if (score === undefined) return 'none';
  if (score >= 85) return 'strong';
  if (score >= 70) return 'apply';
  if (score >= 55) return 'borderline';
  if (score >= 35) return 'low';
  return 'unsuitable';
}

/** Score with a 0–100 rule, the threshold for "Apply" (70) ticked on the rule. */
export function FitRule({ score, size = 'sm', estimate = false }: { score?: number; size?: 'sm' | 'lg'; estimate?: boolean }) {
  return (
    <span className={`fit-rule fit-${size} tone-${scoreTone(score)}${estimate ? ' is-estimate' : ''}`} title={estimate ? 'Quick estimate from the job search; run Analyse fit for the full assessment' : undefined}>
      <span className="fit-num">
        {estimate && score !== undefined && <span className="est">~</span>}
        {score ?? '—'}
      </span>
      <span className="fit-track" aria-hidden="true">
        <span className="fit-fill" style={{ transform: `scaleX(${(score ?? 0) / 100})` }} />
        <span className="fit-tick" />
      </span>
    </span>
  );
}

const statusTone = (s: Status) =>
  ['APPLIED', 'ASSESSMENT', 'INTERVIEW'].includes(s)
    ? 'active'
    : s === 'OFFER'
      ? 'offer'
      : ['REJECTED', 'WITHDRAWN'].includes(s)
        ? 'closed'
        : s === 'NEEDS USER INPUT'
          ? 'open'
          : ['STRONG MATCH', 'PREPARING', 'READY FOR APPROVAL'].includes(s)
            ? 'prep'
            : 'new';

export const statusLabel = (s: string) => s.charAt(0) + s.slice(1).toLowerCase();

export function StatusTag({ value }: { value: Status }) {
  return <span className={`status status-${statusTone(value)}`}>{statusLabel(value)}</span>;
}

export function Field({ label, hint, children, wide }: { label: string; hint?: ReactNode; children: ReactNode; wide?: boolean }) {
  return (
    <label className={`field${wide ? ' field-wide' : ''}`}>
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

export function NoticeBar() {
  const { notice, notify, busy } = useWorkspace();
  const [open, setOpen] = useState(false);
  if (busy)
    return (
      <div className="notice notice-busy" role="status" aria-live="polite">
        <LoaderCircle className="spin" size={18} aria-hidden="true" />
        <span>{busy}…</span>
      </div>
    );
  if (!notice) return null;
  const Icon = notice.tone === 'error' ? CircleAlert : notice.tone === 'success' ? CircleCheck : Info;
  return (
    <div className={`notice notice-${notice.tone}`} role={notice.tone === 'error' ? 'alert' : 'status'} aria-live="polite">
      <Icon size={18} aria-hidden="true" className="notice-icon" />
      <div className="notice-body">
        <p>{notice.message}</p>
        {notice.detail && (
          <button type="button" className="link-button notice-more" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
            {open ? 'Hide technical details' : 'Technical details'}
          </button>
        )}
        {open && notice.detail && <code className="notice-detail">{notice.detail}</code>}
      </div>
      <button
        type="button"
        className="icon-button"
        aria-label="Dismiss message"
        onClick={() => {
          setOpen(false);
          notify(null);
        }}
      >
        <X size={16} />
      </button>
    </div>
  );
}

export const formatDate = (iso?: string) => (iso ? new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—');
export const formatDateTime = (iso?: string) =>
  iso ? new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';

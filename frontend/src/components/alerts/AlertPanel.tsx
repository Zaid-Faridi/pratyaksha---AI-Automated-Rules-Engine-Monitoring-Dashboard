import React, { useState } from 'react';
import { X, CheckCircle, XCircle, Clock, ShieldCheck, AlertTriangle, User, FileText, Image as ImageIcon } from 'lucide-react';
import { Alert, AlertReviewPayload } from '../../types';
import { SeverityBadge } from '../common/SeverityBadge';
import { StatusBadge } from '../common/StatusBadge';

interface AlertPanelProps {
  alert: Alert | null;
  onClose: () => void;
  onReview: (id: number, payload: AlertReviewPayload) => Promise<void>;
  isSubmitting?: boolean;
}

export const AlertPanel: React.FC<AlertPanelProps> = ({
  alert,
  onClose,
  onReview,
  isSubmitting = false,
}) => {
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewerName, setReviewerName] = useState('Monitoring Officer');

  if (!alert) return null;

  const handleAction = async (status: 'verified' | 'dismissed') => {
    await onReview(alert.id, {
      status,
      reviewed_by: reviewerName,
      review_notes: reviewNotes,
    });
    setReviewNotes('');
  };

  const isResolved = alert.status === 'verified' || alert.status === 'dismissed' || alert.status === 'auto_resolved';

  return (
    <div className="fixed inset-0 z-50 overflow-hidden" aria-labelledby="slide-over-title" role="dialog" aria-modal="true">
      {/* Background backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      <div className="fixed inset-y-0 right-0 pl-10 max-w-full flex">
        <div className="w-screen max-w-lg bg-white dark:bg-slate-900 shadow-2xl border-l border-slate-200 dark:border-slate-800 flex flex-col">
          {/* Header */}
          <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-start justify-between bg-slate-50/50 dark:bg-slate-800/40">
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <SeverityBadge severity={alert.severity} />
                <StatusBadge status={alert.status} />
              </div>
              <h2 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4 text-amber-500" />
                {alert.type.replace(/_/g, ' ')}
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Alert ID #{alert.id} • Centre: <span className="font-semibold text-slate-700 dark:text-slate-300">{alert.centre_id}</span>
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
              aria-label="Close alert panel"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Scrollable Content Body */}
          <div className="flex-1 overflow-y-auto p-5 space-y-6 text-sm">
            {/* Alert Message Box */}
            <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block mb-1">
                Discrepancy Details
              </span>
              <p className="text-slate-800 dark:text-slate-200 font-medium leading-relaxed">
                {alert.message}
              </p>
            </div>

            {/* Scope & Metadata */}
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                <span className="text-slate-500 block">Monitored Zone</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200 text-sm mt-0.5 block">
                  {alert.zone || 'Global / Batch Window'}
                </span>
              </div>
              <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                <span className="text-slate-500 block">Assigned Camera</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200 text-sm mt-0.5 block">
                  {alert.camera_id || 'System Auditor'}
                </span>
              </div>
            </div>

            {/* Evidence Thumbnail Section (Privacy Pre-blurred) */}
            <div className="border border-slate-200 dark:border-slate-800 rounded-xl p-4 bg-white dark:bg-slate-900">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                  <ImageIcon className="w-4 h-4 text-teal-600" />
                  Visual Evidence Capture
                </span>
                <span className="text-[10px] text-teal-600 dark:text-teal-400 font-medium flex items-center gap-1 bg-teal-50 dark:bg-teal-950 px-2 py-0.5 rounded">
                  <ShieldCheck className="w-3 h-3" />
                  Privacy-Anonymized
                </span>
              </div>

              {alert.evidence_thumbnail_path ? (
                <div className="relative rounded-lg overflow-hidden border border-slate-200 dark:border-slate-800">
                  <img
                    src={alert.evidence_thumbnail_path}
                    alt="Pre-blurred evidence thumbnail"
                    className="w-full h-44 object-cover"
                  />
                  <div className="absolute bottom-0 inset-x-0 bg-slate-900/80 text-white text-[10px] p-1.5 text-center">
                    Persons pre-blurred by edge detector before saving
                  </div>
                </div>
              ) : (
                <div className="p-4 bg-slate-50 dark:bg-slate-950 rounded-lg text-center text-xs text-slate-500 dark:text-slate-400">
                  <p>No video thumbnail attached.</p>
                  <p className="text-[11px] text-slate-400 mt-1">
                    Edge agent operated in zero-storage privacy mode. Incident logged purely through spatial count audit records.
                  </p>
                </div>
              )}
            </div>

            {/* Timeline */}
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block mb-3 flex items-center gap-1.5">
                <Clock className="w-4 h-4" />
                Audit Lifecycle Timeline
              </span>
              <div className="border-l-2 border-slate-200 dark:border-slate-800 ml-2 space-y-4 text-xs">
                {/* Event 1 */}
                <div className="relative pl-4">
                  <span className="absolute -left-[7px] top-1 w-3 h-3 rounded-full bg-slate-400 border-2 border-white dark:border-slate-900" />
                  <span className="font-semibold text-slate-700 dark:text-slate-300">Detection Trigger Logged</span>
                  <p className="text-slate-500 dark:text-slate-400 text-[11px]">
                    Condition identified over consecutive sampling frames
                  </p>
                </div>
                {/* Event 2 */}
                <div className="relative pl-4">
                  <span className="absolute -left-[7px] top-1 w-3 h-3 rounded-full bg-rose-500 border-2 border-white dark:border-slate-900" />
                  <span className="font-semibold text-slate-800 dark:text-slate-200">Alert Raised</span>
                  <p className="text-slate-500 dark:text-slate-400 text-[11px]">
                    {new Date(alert.created_at).toLocaleString()}
                  </p>
                </div>
                {/* Event 3 (Review or Auto-resolution) */}
                {alert.reviewed_at && (
                  <div className="relative pl-4">
                    <span className="absolute -left-[7px] top-1 w-3 h-3 rounded-full bg-teal-500 border-2 border-white dark:border-slate-900" />
                    <span className="font-semibold text-slate-800 dark:text-slate-200">
                      Status: {alert.status.toUpperCase()}
                    </span>
                    <p className="text-slate-500 dark:text-slate-400 text-[11px]">
                      By {alert.reviewed_by || 'System'} on {new Date(alert.reviewed_at).toLocaleString()}
                    </p>
                    {alert.review_notes && (
                      <p className="mt-1 p-2 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-mono text-[11px]">
                        "{alert.review_notes}"
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Verification Action Form (only if open) */}
            {!isResolved ? (
              <div className="border-t border-slate-200 dark:border-slate-800 pt-5 space-y-3">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 block">
                  Official Verification & Action
                </span>

                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                    Auditor / Reviewer Name
                  </label>
                  <div className="relative">
                    <User className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
                    <input
                      type="text"
                      value={reviewerName}
                      onChange={(e) => setReviewerName(e.target.value)}
                      className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-gov-500 outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                    Reviewer Notes / Action Memo
                  </label>
                  <textarea
                    rows={3}
                    placeholder="e.g., Physical register cross-checked; shortfall confirmed with training partner."
                    value={reviewNotes}
                    onChange={(e) => setReviewNotes(e.target.value)}
                    className="w-full p-2.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-gov-500 outline-none"
                  />
                </div>

                <div className="flex items-center gap-3 pt-2">
                  <button
                    onClick={() => handleAction('verified')}
                    disabled={isSubmitting}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 py-2 px-3 text-xs font-semibold rounded-lg bg-gov-600 hover:bg-gov-700 text-white shadow-sm transition disabled:opacity-50"
                  >
                    <CheckCircle className="w-4 h-4" />
                    Verify Alert
                  </button>
                  <button
                    onClick={() => handleAction('dismissed')}
                    disabled={isSubmitting}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 py-2 px-3 text-xs font-semibold rounded-lg bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 transition disabled:opacity-50"
                  >
                    <XCircle className="w-4 h-4" />
                    Dismiss (False Alarm)
                  </button>
                </div>
              </div>
            ) : (
              <div className="p-3 rounded-lg bg-slate-100 dark:bg-slate-800/60 text-xs text-slate-600 dark:text-slate-400 text-center">
                This alert has been finalized as <span className="font-semibold text-slate-800 dark:text-slate-200">{alert.status}</span>.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

import React from 'react';
import { ComplianceStatus } from '../../types';

interface StatusBadgeProps {
  status: ComplianceStatus | string;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className = '' }) => {
  const norm = status.toUpperCase();

  const config: Record<string, { label: string; style: string }> = {
    COMPLIANT: {
      label: 'Compliant',
      style: 'bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950/70 dark:text-emerald-300 dark:border-emerald-800',
    },
    NEEDS_ATTENTION: {
      label: 'Needs Attention',
      style: 'bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950/70 dark:text-amber-300 dark:border-amber-800',
    },
    NON_COMPLIANT: {
      label: 'Non-Compliant',
      style: 'bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-950/70 dark:text-rose-300 dark:border-rose-800',
    },
    ONLINE: {
      label: 'Online',
      style: 'bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950/70 dark:text-emerald-300 dark:border-emerald-800',
    },
    OFFLINE: {
      label: 'Offline',
      style: 'bg-slate-100 text-slate-800 border-slate-300 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700',
    },
    TAMPERED: {
      label: 'Tampered',
      style: 'bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-950/70 dark:text-rose-300 dark:border-rose-800',
    },
    OPEN: {
      label: 'Open',
      style: 'bg-red-100 text-red-800 border-red-300 dark:bg-red-950/70 dark:text-red-300 dark:border-red-800',
    },
    VERIFIED: {
      label: 'Verified',
      style: 'bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-950/70 dark:text-blue-300 dark:border-blue-800',
    },
    DISMISSED: {
      label: 'Dismissed',
      style: 'bg-slate-100 text-slate-700 border-slate-300 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700',
    },
    AUTO_RESOLVED: {
      label: 'Auto-Resolved',
      style: 'bg-teal-100 text-teal-800 border-teal-300 dark:bg-teal-950/70 dark:text-teal-300 dark:border-teal-800',
    },
  };

  const item = config[norm] || { label: status, style: 'bg-slate-100 text-slate-800 border-slate-300' };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${item.style} ${className}`}>
      {item.label}
    </span>
  );
};

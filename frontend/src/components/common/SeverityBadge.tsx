import React from 'react';
import { Severity } from '../../types';

interface SeverityBadgeProps {
  severity: Severity | string;
  className?: string;
}

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({ severity, className = '' }) => {
  const norm = severity.toUpperCase();

  const colorStyles: Record<string, string> = {
    CRITICAL: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950/70 dark:text-red-300 dark:border-red-800',
    HIGH: 'bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-950/70 dark:text-orange-300 dark:border-orange-800',
    MEDIUM: 'bg-yellow-50 text-yellow-800 border-yellow-200 dark:bg-yellow-950/70 dark:text-yellow-300 dark:border-yellow-800',
    LOW: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/70 dark:text-blue-300 dark:border-blue-800',
    INFO: 'bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/70 dark:text-sky-300 dark:border-sky-800',
  };

  const style = colorStyles[norm] || colorStyles.INFO;

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${style} ${className}`}
      aria-label={`Severity: ${norm}`}
    >
      <span className="w-1.5 h-1.5 rounded-full mr-1.5 bg-current opacity-80" />
      {norm}
    </span>
  );
};

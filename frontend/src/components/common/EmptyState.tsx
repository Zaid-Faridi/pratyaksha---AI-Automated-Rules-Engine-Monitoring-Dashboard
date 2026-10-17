import React from 'react';
import { LucideIcon, Inbox } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: LucideIcon;
  actionText?: string;
  onAction?: () => void;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon: Icon = Inbox,
  actionText,
  onAction,
  className = '',
}) => {
  return (
    <div className={`flex flex-col items-center justify-center p-8 text-center rounded-xl border border-dashed border-slate-300 dark:border-slate-800 ${className}`}>
      <div className="p-3 bg-slate-100 dark:bg-slate-800/80 text-slate-400 dark:text-slate-500 rounded-full mb-3">
        <Icon className="w-8 h-8" aria-hidden="true" />
      </div>
      <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">{title}</h3>
      {description && <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 max-w-sm">{description}</p>}
      {actionText && onAction && (
        <button
          onClick={onAction}
          className="mt-4 px-3 py-1.5 text-xs font-medium rounded-lg bg-gov-600 text-white hover:bg-gov-700 transition"
        >
          {actionText}
        </button>
      )}
    </div>
  );
};

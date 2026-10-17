import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Failed to load data',
  message = 'An unexpected error occurred while communicating with the monitoring backend.',
  onRetry,
  className = '',
}) => {
  return (
    <div className={`p-6 rounded-xl border border-rose-200 dark:border-rose-900/60 bg-rose-50/50 dark:bg-rose-950/20 text-center flex flex-col items-center justify-center ${className}`}>
      <div className="p-2.5 bg-rose-100 dark:bg-rose-900/50 text-rose-600 dark:text-rose-400 rounded-full mb-3">
        <AlertCircle className="w-6 h-6" aria-hidden="true" />
      </div>
      <h4 className="text-sm font-semibold text-rose-800 dark:text-rose-200">{title}</h4>
      <p className="mt-1 text-xs text-rose-600 dark:text-rose-400 max-w-md">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-rose-600 text-white hover:bg-rose-700 transition"
        >
          <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
          Retry Request
        </button>
      )}
    </div>
  );
};

import React from 'react';

interface LoadingSkeletonProps {
  className?: string;
  rows?: number;
}

export const LoadingSkeleton: React.FC<LoadingSkeletonProps> = ({ className = 'h-6 w-full', rows = 1 }) => {
  return (
    <div className="space-y-3 animate-pulse" role="status" aria-label="Loading content...">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className={`bg-slate-200 dark:bg-slate-800 rounded-lg ${className}`}
        />
      ))}
      <span className="sr-only">Loading...</span>
    </div>
  );
};

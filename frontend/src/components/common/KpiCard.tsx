import React from 'react';
import { LucideIcon } from 'lucide-react';

interface KpiCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  variant?: 'default' | 'critical' | 'warning' | 'success' | 'info';
  badge?: string;
  className?: string;
}

export const KpiCard: React.FC<KpiCardProps> = ({
  title,
  value,
  subtitle,
  icon: Icon,
  variant = 'default',
  badge,
  className = '',
}) => {
  const variantStyles = {
    default: {
      card: 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900',
      iconBg: 'bg-gov-50 dark:bg-gov-950 text-gov-600 dark:text-gov-400',
      valueColor: 'text-slate-900 dark:text-slate-50',
    },
    critical: {
      card: 'border-rose-200 dark:border-rose-900/50 bg-rose-50/40 dark:bg-rose-950/20',
      iconBg: 'bg-rose-100 dark:bg-rose-900 text-rose-600 dark:text-rose-300',
      valueColor: 'text-rose-700 dark:text-rose-300',
    },
    warning: {
      card: 'border-amber-200 dark:border-amber-900/50 bg-amber-50/40 dark:bg-amber-950/20',
      iconBg: 'bg-amber-100 dark:bg-amber-900 text-amber-600 dark:text-amber-300',
      valueColor: 'text-amber-700 dark:text-amber-300',
    },
    success: {
      card: 'border-emerald-200 dark:border-emerald-900/50 bg-emerald-50/40 dark:bg-emerald-950/20',
      iconBg: 'bg-emerald-100 dark:bg-emerald-900 text-emerald-600 dark:text-emerald-300',
      valueColor: 'text-emerald-700 dark:text-emerald-300',
    },
    info: {
      card: 'border-teal-200 dark:border-teal-900/50 bg-teal-50/40 dark:bg-teal-950/20',
      iconBg: 'bg-teal-100 dark:bg-teal-900 text-teal-600 dark:text-teal-300',
      valueColor: 'text-teal-700 dark:text-teal-300',
    },
  }[variant];

  return (
    <div
      className={`rounded-xl p-5 border shadow-sm transition-all hover:shadow-md ${variantStyles.card} ${className}`}
      role="region"
      aria-label={`${title}: ${value}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          {title}
        </span>
        <div className={`p-2.5 rounded-lg ${variantStyles.iconBg}`}>
          <Icon className="w-5 h-5" aria-hidden="true" />
        </div>
      </div>

      <div className="mt-3 flex items-baseline justify-between">
        <span className={`text-2xl lg:text-3xl font-extrabold tracking-tight ${variantStyles.valueColor}`}>
          {value}
        </span>
        {badge && (
          <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
            {badge}
          </span>
        )}
      </div>

      {subtitle && (
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1">
          {subtitle}
        </p>
      )}
    </div>
  );
};

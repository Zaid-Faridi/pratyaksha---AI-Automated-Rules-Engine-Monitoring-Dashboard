import React, { useState, useMemo } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ShieldAlert,
  ArrowRight,
  Users,
  Wrench,
  AlertTriangle,
  HardHat,
  Flame,
  Layers,
  UserX,
  FileText,
  VideoOff,
  Activity,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

import { Alert } from '../../types';
import { api } from '../../api/client';
import {
  computeAlertMetrics,
  SEVERITY_COLORS,
  AlertSeverityKey,
} from '../../utils/alertMetrics';

interface ActiveAlertsPanelProps {
  alerts?: Alert[];
  alertsByType?: Record<string, number>;
  alertsBySeverity?: Record<string, number>;
  totalAlerts?: number;
  isLoading?: boolean;
}

const ALERT_ICONS: Record<string, React.FC<{ className?: string }>> = {
  ATTENDANCE_MISMATCH: Users,
  INFRASTRUCTURE_GAP: Wrench,
  EQUIPMENT_MISSING: Wrench,
  NON_FUNCTIONAL_EQUIPMENT: AlertTriangle,
  EQUIPMENT_INOPERABLE: AlertTriangle,
  PPE_VIOLATION: HardHat,
  SAFETY_EQUIPMENT_MISSING: Flame,
  CAPACITY_DEFICIT: Layers,
  INSTRUCTOR_ABSENT: UserX,
  MANDATORY_SIGNAGE_MISSING: FileText,
  SIGNAGE_MISSING: FileText,
  CAMERA_OFFLINE: VideoOff,
  CAMERA_TAMPER: VideoOff,
  STREAM_TAMPERING: VideoOff,
  POOR_CAMERA_QUALITY: VideoOff,
  ZONE_IDLE_DURING_BATCH: Activity,
  GHOST_WORKER: Users,
  UNREGISTERED_BATCH: ShieldAlert,
};

export const ActiveAlertsPanel: React.FC<ActiveAlertsPanelProps> = ({
  alerts: propAlerts,
  alertsByType: fallbackByType,
  alertsBySeverity: fallbackBySeverity,
  totalAlerts: fallbackTotal,
  isLoading: propLoading = false,
}) => {
  const navigate = useNavigate();
  const [showAll, setShowAll] = useState(false);

  // Self-fetch open alerts if not supplied by parent
  const { data: fetchedAlerts, isLoading: queryLoading } = useQuery({
    queryKey: ['openAlertsPanelList'],
    queryFn: () => api.getAlerts({ status: 'open' }),
    enabled: propAlerts === undefined,
    refetchInterval: 15000,
  });

  const isLoading = propLoading || (propAlerts === undefined && queryLoading);

  // Single Source of Truth computation
  const metrics = useMemo(() => {
    const sourceAlerts = propAlerts !== undefined ? propAlerts : fetchedAlerts;
    if (sourceAlerts && Array.isArray(sourceAlerts)) {
      return computeAlertMetrics(sourceAlerts);
    }

    // Fallback synthesis if alerts array is unavailable
    if (fallbackByType) {
      const syntheticAlerts: { type: string; severity: string; status: string }[] = [];
      Object.entries(fallbackByType).forEach(([type, count]) => {
        for (let i = 0; i < count; i++) {
          syntheticAlerts.push({ type, severity: 'HIGH', status: 'open' });
        }
      });
      return computeAlertMetrics(syntheticAlerts);
    }

    return computeAlertMetrics([]);
  }, [propAlerts, fetchedAlerts, fallbackByType, fallbackBySeverity, fallbackTotal]);

  const { totalAlerts, severityCounts, typeItems, maxCount } = metrics;
  const visibleList = showAll ? typeItems : typeItems.slice(0, 5);

  // Loading Skeleton
  if (isLoading) {
    return (
      <div className="p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm animate-pulse flex flex-col justify-between h-full">
        <div>
          <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
            <div className="space-y-1.5">
              <div className="h-4 w-32 bg-slate-200 dark:bg-slate-800 rounded" />
              <div className="h-3 w-52 bg-slate-100 dark:bg-slate-800/60 rounded" />
            </div>
            <div className="h-4 w-20 bg-slate-200 dark:bg-slate-800 rounded" />
          </div>
          <div className="my-4 h-16 bg-slate-100 dark:bg-slate-800/50 rounded-xl" />
          <div className="space-y-3 mt-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-10 bg-slate-100 dark:bg-slate-800/40 rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col justify-between h-full transition-all">
      {/* 1. Header */}
      <div>
        <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
              <ShieldAlert className="w-4 h-4 text-gov-600 dark:text-gov-400" aria-hidden="true" />
              Active Alerts
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Open alerts by type. Colour shows severity.
            </p>
          </div>
          <Link
            to="/alerts"
            className="text-xs font-semibold text-gov-600 hover:text-gov-700 dark:text-gov-400 dark:hover:text-gov-300 inline-flex items-center gap-1 transition group"
            aria-label="View Queue: Open compliance alert queue"
          >
            View Queue{' '}
            <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" aria-hidden="true" />
          </Link>
        </div>

        {totalAlerts === 0 ? (
          /* Empty State */
          <div className="flex flex-col items-center justify-center py-12 px-4 text-center my-6">
            <div className="w-12 h-12 rounded-full bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 flex items-center justify-center mb-3">
              <CheckCircle2 className="w-6 h-6 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
            </div>
            <p className="text-sm font-bold text-slate-800 dark:text-slate-200">No open alerts.</p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-sm">
              All centres are within limits.
            </p>
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            {/* 2. Summary Strip */}
            <div className="p-3.5 sm:p-4 rounded-xl bg-slate-50/80 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-800 space-y-2.5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                {/* Total Counter */}
                <div className="flex items-baseline gap-1.5 flex-shrink-0">
                  <span className="text-2xl sm:text-3xl font-black text-slate-900 dark:text-slate-50 tracking-tight tabular-nums leading-none">
                    {totalAlerts}
                  </span>
                  <span className="text-xs sm:text-sm font-semibold text-slate-600 dark:text-slate-400">
                    open {totalAlerts === 1 ? 'alert' : 'alerts'}
                  </span>
                </div>

                {/* Single Horizontal Stacked Bar */}
                <div className="flex-1 min-w-[140px] sm:max-w-xs md:max-w-sm">
                  <div
                    className="h-3 w-full bg-slate-200/80 dark:bg-slate-700/60 rounded-full overflow-hidden flex shadow-inner"
                    role="progressbar"
                    aria-label={`Open alerts severity breakdown: ${severityCounts.CRITICAL} Critical, ${severityCounts.HIGH} High, ${severityCounts.MEDIUM} Medium, ${severityCounts.LOW} Low`}
                  >
                    {severityCounts.CRITICAL > 0 && (
                      <div
                        style={{
                          width: `${(severityCounts.CRITICAL / totalAlerts) * 100}%`,
                          backgroundColor: SEVERITY_COLORS.CRITICAL,
                        }}
                        className="h-full transition-all duration-700 ease-out"
                        title={`Critical: ${severityCounts.CRITICAL}`}
                      />
                    )}
                    {severityCounts.HIGH > 0 && (
                      <div
                        style={{
                          width: `${(severityCounts.HIGH / totalAlerts) * 100}%`,
                          backgroundColor: SEVERITY_COLORS.HIGH,
                        }}
                        className="h-full transition-all duration-700 ease-out"
                        title={`High: ${severityCounts.HIGH}`}
                      />
                    )}
                    {severityCounts.MEDIUM > 0 && (
                      <div
                        style={{
                          width: `${(severityCounts.MEDIUM / totalAlerts) * 100}%`,
                          backgroundColor: SEVERITY_COLORS.MEDIUM,
                        }}
                        className="h-full transition-all duration-700 ease-out"
                        title={`Medium: ${severityCounts.MEDIUM}`}
                      />
                    )}
                    {severityCounts.LOW > 0 && (
                      <div
                        style={{
                          width: `${(severityCounts.LOW / totalAlerts) * 100}%`,
                          backgroundColor: SEVERITY_COLORS.LOW,
                        }}
                        className="h-full transition-all duration-700 ease-out"
                        title={`Low: ${severityCounts.LOW}`}
                      />
                    )}
                  </div>
                </div>
              </div>

              {/* Legend under bar: Full words and counts, never truncated */}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs pt-2 border-t border-slate-200/60 dark:border-slate-700/50">
                {(
                  [
                    { key: 'CRITICAL', label: 'Critical' },
                    { key: 'HIGH', label: 'High' },
                    { key: 'MEDIUM', label: 'Medium' },
                    { key: 'LOW', label: 'Low' },
                  ] as { key: AlertSeverityKey; label: string }[]
                ).map(({ key, label }) => {
                  const count = severityCounts[key];
                  const isZero = count === 0;

                  return (
                    <button
                      key={key}
                      type="button"
                      disabled={isZero}
                      onClick={() => !isZero && navigate(`/alerts?severity=${key}`)}
                      className={`flex items-center gap-1.5 font-medium transition focus:outline-none focus:ring-1 focus:ring-gov-500 rounded px-1 -mx-1 ${
                        isZero
                          ? 'opacity-35 cursor-default'
                          : 'text-slate-700 dark:text-slate-200 hover:text-slate-900 dark:hover:text-white cursor-pointer'
                      }`}
                      aria-label={`${label} ${count}`}
                    >
                      <span
                        className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                        style={{ backgroundColor: SEVERITY_COLORS[key] }}
                      />
                      <span>
                        {label} {count}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 3. Ranked List of Alert Types */}
            <div className="space-y-1.5" role="list" aria-label="Ranked alert types by frequency">
              {visibleList.map((item) => {
                const IconComponent = ALERT_ICONS[item.type] || AlertTriangle;

                // Build accessible ARIA description
                const sevParts: string[] = [];
                if (item.severities.CRITICAL > 0) sevParts.push(`${item.severities.CRITICAL} critical`);
                if (item.severities.HIGH > 0) sevParts.push(`${item.severities.HIGH} high`);
                if (item.severities.MEDIUM > 0) sevParts.push(`${item.severities.MEDIUM} medium`);
                if (item.severities.LOW > 0) sevParts.push(`${item.severities.LOW} low`);
                const sevDescription = sevParts.join(', ');
                const rowAriaLabel = `${item.label}, ${item.count} ${item.count === 1 ? 'alert' : 'alerts'}${
                  sevDescription ? `: ${sevDescription}` : ''
                }`;

                return (
                  <button
                    key={item.type}
                    type="button"
                    onClick={() => navigate(`/alerts?type=${item.type}`)}
                    className="w-full grid grid-cols-[32px_1fr_120px_32px] sm:grid-cols-[32px_1fr_140px_36px] items-center gap-2.5 sm:gap-3 p-2 rounded-xl hover:bg-slate-50 dark:hover:bg-slate-800/60 focus:outline-none focus:ring-2 focus:ring-gov-500 border border-transparent hover:border-slate-200/80 dark:hover:border-slate-700/80 transition text-left cursor-pointer group"
                    aria-label={rowAriaLabel}
                    title={rowAriaLabel}
                  >
                    {/* Column 1: Icon (32px) */}
                    <div className="w-8 h-8 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 flex items-center justify-center flex-shrink-0 group-hover:bg-gov-50 dark:group-hover:bg-gov-950/80 group-hover:text-gov-600 dark:group-hover:text-gov-400 transition-colors">
                      <IconComponent className="w-4 h-4" aria-hidden="true" />
                    </div>

                    {/* Column 2: Full Alert Type Name (No truncation, wraps to 2 lines if needed) */}
                    <span className="min-w-0 text-xs sm:text-sm font-semibold text-slate-800 dark:text-slate-200 group-hover:text-gov-600 dark:group-hover:text-gov-400 transition-colors leading-tight line-clamp-2">
                      {item.label}
                    </span>

                    {/* Column 3: Segmented Bar (Fixed 120-140px wide, scaled to maxCount) */}
                    <div
                      className="w-[120px] sm:w-[140px] h-2.5 sm:h-3 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden flex flex-shrink-0 shadow-inner"
                      aria-hidden="true"
                    >
                      {item.severities.CRITICAL > 0 && (
                        <div
                          style={{
                            width: `${(item.severities.CRITICAL / maxCount) * 100}%`,
                            backgroundColor: SEVERITY_COLORS.CRITICAL,
                          }}
                          className="h-full transition-all duration-700 ease-out"
                        />
                      )}
                      {item.severities.HIGH > 0 && (
                        <div
                          style={{
                            width: `${(item.severities.HIGH / maxCount) * 100}%`,
                            backgroundColor: SEVERITY_COLORS.HIGH,
                          }}
                          className="h-full transition-all duration-700 ease-out"
                        />
                      )}
                      {item.severities.MEDIUM > 0 && (
                        <div
                          style={{
                            width: `${(item.severities.MEDIUM / maxCount) * 100}%`,
                            backgroundColor: SEVERITY_COLORS.MEDIUM,
                          }}
                          className="h-full transition-all duration-700 ease-out"
                        />
                      )}
                      {item.severities.LOW > 0 && (
                        <div
                          style={{
                            width: `${(item.severities.LOW / maxCount) * 100}%`,
                            backgroundColor: SEVERITY_COLORS.LOW,
                          }}
                          className="h-full transition-all duration-700 ease-out"
                        />
                      )}
                    </div>

                    {/* Column 4: Count (Right-aligned, tabular numbers) */}
                    <span className="text-right text-xs sm:text-sm font-bold text-slate-900 dark:text-slate-100 tabular-nums">
                      {item.count}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* 4. Show all / Show top 5 toggle (hidden if 5 or fewer) */}
      {typeItems.length > 5 && (
        <div className="pt-3 mt-3 border-t border-slate-100 dark:border-slate-800 flex justify-end">
          <button
            type="button"
            onClick={() => setShowAll(!showAll)}
            className="text-xs font-semibold text-gov-600 dark:text-gov-400 hover:text-gov-700 dark:hover:text-gov-300 inline-flex items-center gap-1 transition"
            aria-expanded={showAll}
          >
            {showAll ? (
              <>
                Show top 5 <ChevronUp className="w-3.5 h-3.5" aria-hidden="true" />
              </>
            ) : (
              <>
                Show all {typeItems.length} types <ChevronDown className="w-3.5 h-3.5" aria-hidden="true" />
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
};

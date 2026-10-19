import React, { useState, useMemo } from 'react';
import { useNavigate, Link } from 'react-router-dom';
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
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts';

interface ActiveAlertsPanelProps {
  alertsByType?: Record<string, number>;
  alertsBySeverity?: Record<string, number>;
  totalAlerts?: number;
  isLoading?: boolean;
}

// Canonical alert type metadata mapping
const ALERT_TYPE_META: Record<
  string,
  { label: string; icon: React.FC<{ className?: string }>; severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' }
> = {
  ATTENDANCE_MISMATCH: { label: 'Attendance Mismatch', icon: Users, severity: 'HIGH' },
  EQUIPMENT_MISSING: { label: 'Infrastructure Gap', icon: Wrench, severity: 'HIGH' },
  EQUIPMENT_INOPERABLE: { label: 'Non-Functional Equipment', icon: AlertTriangle, severity: 'MEDIUM' },
  NON_FUNCTIONAL_EQUIPMENT: { label: 'Non-Functional Equipment', icon: AlertTriangle, severity: 'MEDIUM' },
  PPE_VIOLATION: { label: 'PPE Violation', icon: HardHat, severity: 'MEDIUM' },
  SAFETY_EQUIPMENT_MISSING: { label: 'Safety Equipment Missing', icon: Flame, severity: 'HIGH' },
  CAPACITY_DEFICIT: { label: 'Capacity Deficit', icon: Layers, severity: 'HIGH' },
  INSTRUCTOR_ABSENT: { label: 'Instructor Absent', icon: UserX, severity: 'HIGH' },
  MANDATORY_SIGNAGE_MISSING: { label: 'Signage Missing', icon: FileText, severity: 'MEDIUM' },
  CAMERA_OFFLINE: { label: 'Camera Offline', icon: VideoOff, severity: 'CRITICAL' },
  STREAM_TAMPERING: { label: 'Stream Tampering', icon: VideoOff, severity: 'CRITICAL' },
  ZONE_IDLE_DURING_BATCH: { label: 'Zone Idle During Batch', icon: Activity, severity: 'LOW' },
  GHOST_WORKER: { label: 'Ghost Worker Discrepancy', icon: Users, severity: 'CRITICAL' },
  UNREGISTERED_BATCH: { label: 'Unregistered Batch', icon: ShieldAlert, severity: 'MEDIUM' },
};

// Accessible severity color tokens consistent with app design language
const SEVERITY_CONFIG: Record<
  string,
  { label: string; color: string; bgClass: string; textClass: string; borderClass: string; weight: number }
> = {
  CRITICAL: {
    label: 'Critical',
    color: '#EF4444',
    bgClass: 'bg-rose-50 dark:bg-rose-950/60',
    textClass: 'text-rose-700 dark:text-rose-300',
    borderClass: 'border-rose-200 dark:border-rose-800',
    weight: 4,
  },
  HIGH: {
    label: 'High',
    color: '#F97316',
    bgClass: 'bg-orange-50 dark:bg-orange-950/60',
    textClass: 'text-orange-700 dark:text-orange-300',
    borderClass: 'border-orange-200 dark:border-orange-800',
    weight: 3,
  },
  MEDIUM: {
    label: 'Medium',
    color: '#F59E0B',
    bgClass: 'bg-amber-50 dark:bg-amber-950/60',
    textClass: 'text-amber-700 dark:text-amber-300',
    borderClass: 'border-amber-200 dark:border-amber-800',
    weight: 2,
  },
  LOW: {
    label: 'Low',
    color: '#3B82F6',
    bgClass: 'bg-blue-50 dark:bg-blue-950/60',
    textClass: 'text-blue-700 dark:text-blue-300',
    borderClass: 'border-blue-200 dark:border-blue-800',
    weight: 1,
  },
};

export const ActiveAlertsPanel: React.FC<ActiveAlertsPanelProps> = ({
  alertsByType = {},
  alertsBySeverity = {},
  totalAlerts = 0,
  isLoading = false,
}) => {
  const navigate = useNavigate();
  const [showAll, setShowAll] = useState(false);

  // Donut chart dataset
  const donutData = useMemo(() => {
    return ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
      .map((sev) => {
        const count = alertsBySeverity[sev] || 0;
        return {
          name: SEVERITY_CONFIG[sev].label,
          severityKey: sev,
          value: count,
          color: SEVERITY_CONFIG[sev].color,
        };
      })
      .filter((d) => d.value > 0);
  }, [alertsBySeverity]);

  // Ranked list of alert types sorted by count descending, then severity weight
  const rankedAlertTypes = useMemo(() => {
    const items = Object.entries(alertsByType).map(([type, count]) => {
      const meta = ALERT_TYPE_META[type] || {
        label: type.replace(/_/g, ' '),
        icon: AlertTriangle,
        severity: 'MEDIUM' as const,
      };
      const sevMeta = SEVERITY_CONFIG[meta.severity] || SEVERITY_CONFIG.MEDIUM;
      return {
        rawType: type,
        label: meta.label,
        count,
        icon: meta.icon,
        severity: meta.severity,
        severityMeta: sevMeta,
      };
    });

    // Sort by count desc, then severity weight desc
    items.sort((a, b) => {
      if (b.count !== a.count) return b.count - a.count;
      return b.severityMeta.weight - a.severityMeta.weight;
    });

    return items;
  }, [alertsByType]);

  const maxCount = useMemo(() => {
    return Math.max(...rankedAlertTypes.map((i) => i.count), 1);
  }, [rankedAlertTypes]);

  const visibleList = showAll ? rankedAlertTypes : rankedAlertTypes.slice(0, 6);

  if (isLoading) {
    return (
      <div className="p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm animate-pulse">
        <div className="h-6 w-48 bg-slate-200 dark:bg-slate-800 rounded mb-4" />
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
          <div className="md:col-span-5 h-56 bg-slate-100 dark:bg-slate-800/60 rounded-xl" />
          <div className="md:col-span-7 space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-9 bg-slate-100 dark:bg-slate-800/60 rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col justify-between h-full transition-all">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100 dark:border-slate-800">
        <div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
            <ShieldAlert className="w-4 h-4 text-gov-600 dark:text-gov-400" aria-hidden="true" />
            Active Alerts Breakdown
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Severity distribution and ranked violation categories
          </p>
        </div>
        <Link
          to="/alerts"
          className="text-xs font-semibold text-gov-600 hover:text-gov-700 dark:text-gov-400 dark:hover:text-gov-300 inline-flex items-center gap-1 transition"
          aria-label="View all active compliance alerts in queue"
        >
          View Queue <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
        </Link>
      </div>

      {totalAlerts === 0 ? (
        /* Empty State */
        <div className="flex flex-col items-center justify-center py-10 px-4 text-center my-auto">
          <div className="w-12 h-12 rounded-full bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 flex items-center justify-center mb-3">
            <CheckCircle2 className="w-6 h-6 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
          </div>
          <p className="text-sm font-bold text-slate-800 dark:text-slate-200">No Open Alerts</p>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-sm">
            All registered skilling centres are currently operating within compliance thresholds.
          </p>
        </div>
      ) : (
        /* Two-part panel: Left Donut + Right Ranked List */
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-center flex-1">
          {/* Part A: Severity Donut Chart (5 cols) */}
          <div className="md:col-span-5 flex flex-col items-center justify-center p-2 rounded-xl bg-slate-50/50 dark:bg-slate-800/30 border border-slate-100 dark:border-slate-800/80">
            <div className="relative w-full max-w-[170px] h-[150px] flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={donutData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={46}
                    outerRadius={66}
                    paddingAngle={3}
                    stroke="none"
                    onClick={(entry) => {
                      if (entry && entry.severityKey) {
                        navigate(`/alerts?severity=${entry.severityKey}`);
                      }
                    }}
                    className="cursor-pointer focus:outline-none"
                    role="img"
                    aria-label={`Donut chart showing ${totalAlerts} total alerts by severity`}
                  >
                    {donutData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={entry.color}
                        className="hover:opacity-85 transition-opacity"
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0F172A',
                      borderColor: '#334155',
                      borderRadius: '8px',
                      color: '#F8FAFC',
                      fontSize: '11px',
                      padding: '6px 10px',
                    }}
                    formatter={(val: number, name: string) => [`${val} alerts`, name]}
                  />
                </PieChart>
              </ResponsiveContainer>

              {/* Total readout in centre */}
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-2xl font-black text-slate-900 dark:text-slate-50 tracking-tight leading-none">
                  {totalAlerts}
                </span>
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mt-1">
                  Total
                </span>
              </div>
            </div>

            {/* Compact Severity Legend */}
            <div className="grid grid-cols-2 gap-1.5 w-full mt-2 pt-2 border-t border-slate-200/60 dark:border-slate-700/60 text-xs">
              {(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((sevKey) => {
                const count = alertsBySeverity[sevKey] || 0;
                const meta = SEVERITY_CONFIG[sevKey];
                return (
                  <button
                    key={sevKey}
                    type="button"
                    onClick={() => navigate(`/alerts?severity=${sevKey}`)}
                    className="flex items-center justify-between px-2 py-1 rounded-md text-[11px] font-medium text-slate-600 dark:text-slate-300 hover:bg-white dark:hover:bg-slate-700/60 transition shadow-none hover:shadow-xs"
                    title={`Click to filter alerts by ${meta.label} severity`}
                    aria-label={`${count} ${meta.label} severity alerts`}
                  >
                    <span className="flex items-center gap-1.5 truncate">
                      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: meta.color }} />
                      <span className="truncate">{meta.label}</span>
                    </span>
                    <span className="font-bold ml-1 text-slate-900 dark:text-slate-100">{count}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Part B: Ranked List of Alert Types (7 cols) */}
          <div className="md:col-span-7 flex flex-col justify-between space-y-2">
            <div className="space-y-1.5" role="list" aria-label="Ranked alert types">
              {visibleList.map((item) => {
                const IconComponent = item.icon;
                const barPercent = Math.min(100, Math.max(8, (item.count / maxCount) * 100));

                return (
                  <button
                    key={item.rawType}
                    type="button"
                    onClick={() => navigate(`/alerts?type=${item.rawType}`)}
                    className="w-full group flex items-center justify-between gap-3 p-1.5 px-2 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/60 border border-transparent hover:border-slate-200/70 dark:hover:border-slate-700/60 transition text-left cursor-pointer min-w-0"
                    title={`Click to view ${item.count} ${item.label} alerts`}
                    aria-label={`${item.label}: ${item.count} alerts, ${item.severityMeta.label} severity`}
                  >
                    {/* Left: Icon + Label (Single line, no wrapping) */}
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <div
                        className={`p-1 rounded-md flex-shrink-0 ${item.severityMeta.bgClass} ${item.severityMeta.textClass}`}
                      >
                        <IconComponent className="w-3.5 h-3.5" aria-hidden="true" />
                      </div>
                      <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 truncate group-hover:text-gov-600 dark:group-hover:text-gov-400 transition-colors">
                        {item.label}
                      </span>
                    </div>

                    {/* Middle: Proportional Progress Bar */}
                    <div className="w-16 sm:w-24 hidden sm:block h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden flex-shrink-0">
                      <div
                        className="h-full rounded-full transition-all duration-500 ease-out"
                        style={{
                          width: `${barPercent}%`,
                          backgroundColor: item.severityMeta.color,
                        }}
                      />
                    </div>

                    {/* Right: Count + Severity Chip */}
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className="text-xs font-bold text-slate-900 dark:text-slate-100 min-w-[18px] text-right">
                        {item.count}
                      </span>
                      <span
                        className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${item.severityMeta.bgClass} ${item.severityMeta.textClass} ${item.severityMeta.borderClass}`}
                      >
                        {item.severityMeta.label}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Toggle show all / show less */}
            {rankedAlertTypes.length > 6 && (
              <div className="pt-2 flex justify-end">
                <button
                  type="button"
                  onClick={() => setShowAll(!showAll)}
                  className="text-[11px] font-semibold text-gov-600 dark:text-gov-400 hover:text-gov-700 dark:hover:text-gov-300 inline-flex items-center gap-1 transition"
                  aria-expanded={showAll}
                >
                  {showAll ? (
                    <>
                      Show Top 6 <ChevronUp className="w-3.5 h-3.5" />
                    </>
                  ) : (
                    <>
                      Show all ({rankedAlertTypes.length}) <ChevronDown className="w-3.5 h-3.5" />
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

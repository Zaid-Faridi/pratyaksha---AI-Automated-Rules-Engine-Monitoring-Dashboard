import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Building2,
  AlertTriangle,
  Users,
  VideoOff,
  CheckCircle2,
  TrendingUp,
  ArrowRight,
  ShieldAlert,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  AreaChart,
  Area,
  CartesianGrid,
} from 'recharts';

import { api } from '../api/client';
import { KpiCard } from '../components/common/KpiCard';
import { ScoreRing } from '../components/common/ScoreRing';
import { StatusBadge } from '../components/common/StatusBadge';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { ErrorState } from '../components/common/ErrorState';
import { ActiveAlertsPanel } from '../components/dashboard/ActiveAlertsPanel';
import { LiveCentreWall } from '../components/dashboard/LiveCentreWall';

export const OverviewPage: React.FC = () => {
  const { data: summary, isLoading, isError, refetch } = useQuery({
    queryKey: ['dashboardSummary'],
    queryFn: () => api.getDashboardSummary(),
    refetchInterval: 30000, // Auto-refresh every 30s
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
          <LoadingSkeleton rows={1} className="h-32" />
          <LoadingSkeleton rows={1} className="h-32" />
          <LoadingSkeleton rows={1} className="h-32" />
          <LoadingSkeleton rows={1} className="h-32" />
          <LoadingSkeleton rows={1} className="h-32" />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <LoadingSkeleton rows={1} className="h-80" />
          <LoadingSkeleton rows={1} className="h-80" />
        </div>
        <LoadingSkeleton rows={5} className="h-14" />
      </div>
    );
  }

  if (isError || !summary) {
    return <ErrorState onRetry={() => refetch()} />;
  }

  return (
    <div className="space-y-7 pb-10">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight">
            Monitoring & Compliance Overview
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
            Real-time video analytics for government-sanctioned skilling centres.
          </p>
        </div>

        {/* Ministry-Ready Report Exports */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2">
          <a
            href={api.getReportCsvUrl()}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 shadow-sm transition"
          >
            <span>Export CSV Report</span>
          </a>
          <a
            href={api.getReportPdfUrl()}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold bg-gov-600 hover:bg-gov-700 text-white shadow-sm transition"
          >
            <span>Official Ministry PDF</span>
          </a>
        </div>
      </div>

      <div className="text-[11px] text-slate-400 dark:text-slate-500 italic -mt-4">
        * Official reports compiled strictly from aggregate entity headcounts. No facial biometrics or personally identifiable data is recorded.
      </div>

      {/* 5 Top KPI Cards */}
      <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
        <KpiCard
          title="Centres"
          value={summary.total_centres}
          subtitle="Across 6 states"
          icon={Building2}
          variant="default"
        />

        <KpiCard
          title="Avg compliance"
          value={`${summary.average_compliance_score.toFixed(1)}%`}
          subtitle="National benchmark"
          topRightNode={
            <ScoreRing
              score={summary.average_compliance_score}
              size="sm"
              showLabel={false}
            />
          }
          variant="default"
        />

        <KpiCard
          title="Open alerts"
          value={summary.open_alerts_count}
          subtitle={`${summary.alerts_by_severity?.CRITICAL || 0} critical`}
          icon={AlertTriangle}
          variant={summary.open_alerts_count > 0 ? 'critical' : 'success'}
        />

        <KpiCard
          title="Low attendance"
          value={summary.attendance_mismatches_today}
          subtitle="Batches below 70%"
          icon={Users}
          variant={summary.attendance_mismatches_today > 0 ? 'warning' : 'success'}
        />

        <KpiCard
          title="Cameras offline"
          value={summary.offline_cameras}
          subtitle={`${summary.online_cameras} of ${summary.total_cameras} operational`}
          icon={VideoOff}
          variant={summary.offline_cameras > 0 ? 'critical' : 'success'}
        />
      </div>

      {/* Live Centre Wall Section */}
      <LiveCentreWall />

      {/* Charts Section: Alerts Breakdown & Compliance Trend */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Replaced Active Alerts Breakdown Panel */}
        <ActiveAlertsPanel
          alertsByType={summary.alerts_by_type}
          alertsBySeverity={summary.alerts_by_severity}
          totalAlerts={summary.open_alerts_count}
        />

        {/* 7-Day Compliance Trend */}
        <div className="p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col justify-between h-full">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                <TrendingUp className="w-4 h-4 text-teal-600" />
                7-Day Compliance Index Trend
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Weighted composite score average across centres
              </p>
            </div>
            <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2.5 py-1 rounded-full border border-emerald-200 dark:border-emerald-800">
              Target &ge; 85%
            </span>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={summary.compliance_trend} margin={{ top: 10, right: 20, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="complianceGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0D9488" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#0D9488" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis domain={[50, 100]} tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0F172A',
                    borderColor: '#334155',
                    borderRadius: '8px',
                    color: '#F8FAFC',
                    fontSize: '12px',
                  }}
                  formatter={(val: number) => [`${val.toFixed(1)}%`, 'Average Score']}
                />
                <Area
                  type="monotone"
                  dataKey="average_score"
                  stroke="#0D9488"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#complianceGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Top Non-Compliant Centres Table (User requirement 1: Table of least compliant centres) */}
      <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
        <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
              Priority Focus: Least Compliant Skilling Centres
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Ranked ascending by compliance deficit requiring administrative audit
            </p>
          </div>
          <Link
            to="/centres"
            className="text-xs font-semibold text-gov-600 hover:text-gov-700 dark:text-gov-400 inline-flex items-center gap-1"
          >
            All Centres <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 font-semibold uppercase tracking-wider">
                <th className="p-3.5">Centre Name</th>
                <th className="p-3.5 text-center">Compliance Score</th>
                <th className="p-3.5 text-center">Attendance Rate</th>
                <th className="p-3.5 text-center">Infra Availability</th>
                <th className="p-3.5 text-center">Camera Uptime</th>
                <th className="p-3.5 text-center">Open Alerts</th>
                <th className="p-3.5 text-center">Audit Status</th>
                <th className="p-3.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/70">
              {summary.top_non_compliant_centres.map((centre) => (
                <tr key={centre.centre_id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition">
                  <td className="p-3.5 font-medium text-slate-900 dark:text-slate-100">
                    <Link
                      to={`/centres/${centre.centre_id}`}
                      className="hover:text-gov-600 dark:hover:text-gov-400 font-semibold"
                    >
                      {centre.centre_name}
                    </Link>
                    <span className="block text-[10px] text-slate-400 font-normal">ID: {centre.centre_id}</span>
                  </td>
                  <td className="p-3.5 text-center">
                    <div className="inline-flex items-center gap-2">
                      <ScoreRing score={centre.compliance_score} size="sm" />
                      <span className="font-bold text-xs">{centre.compliance_score.toFixed(1)}%</span>
                    </div>
                  </td>
                  <td className="p-3.5 text-center font-medium">
                    <span className={centre.attendance_rate < 0.70 ? 'text-rose-600 font-bold' : ''}>
                      {(centre.attendance_rate * 100).toFixed(0)}%
                    </span>
                  </td>
                  <td className="p-3.5 text-center font-medium">
                    <span className={centre.infrastructure_availability_rate < 0.85 ? 'text-amber-600 font-bold' : ''}>
                      {(centre.infrastructure_availability_rate * 100).toFixed(0)}%
                    </span>
                  </td>
                  <td className="p-3.5 text-center font-medium">
                    <span className={centre.camera_uptime_rate < 0.50 ? 'text-rose-600 font-bold' : ''}>
                      {(centre.camera_uptime_rate * 100).toFixed(0)}%
                    </span>
                  </td>
                  <td className="p-3.5 text-center">
                    {centre.open_alerts_count > 0 ? (
                      <span className="inline-flex px-2 py-0.5 text-xs font-bold rounded-full bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300">
                        {centre.open_alerts_count}
                      </span>
                    ) : (
                      <span className="text-slate-400 text-xs">0</span>
                    )}
                  </td>
                  <td className="p-3.5 text-center">
                    <StatusBadge status={centre.summary_status} />
                  </td>
                  <td className="p-3.5 text-right">
                    <Link
                      to={`/centres/${centre.centre_id}`}
                      className="inline-flex items-center gap-1 text-xs font-semibold text-gov-600 hover:text-gov-800 dark:text-gov-400 dark:hover:text-gov-300"
                    >
                      Audit <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

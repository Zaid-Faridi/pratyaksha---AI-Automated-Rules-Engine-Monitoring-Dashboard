import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  History,
  ShieldCheck,
  Filter,
  RefreshCw,
  Search,
  Building,
  CheckCircle2,
  XCircle,
  FileText,
  Clock,
  UserCheck,
} from 'lucide-react';
import { api } from '../api/client';
import { AuditLog, Centre } from '../types';

export const AuditLogPage: React.FC = () => {
  const [selectedCentre, setSelectedCentre] = useState<string>('');
  const [selectedAction, setSelectedAction] = useState<string>('');
  const [officerFilter, setOfficerFilter] = useState<string>('');

  // Fetch Centres for filter
  const { data: centres = [] } = useQuery({
    queryKey: ['centres'],
    queryFn: () => api.getCentres(),
  });

  // Fetch Audit Logs
  const {
    data: logs = [],
    isLoading,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['auditLogs', selectedCentre, selectedAction, officerFilter],
    queryFn: () =>
      api.getAuditLogs({
        centre_id: selectedCentre || undefined,
        action: selectedAction || undefined,
        officer_name: officerFilter || undefined,
      }),
    refetchInterval: 15000,
  });

  const getActionBadge = (action: string) => {
    switch (action.toUpperCase()) {
      case 'VERIFIED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            Verified
          </span>
        );
      case 'DISMISSED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
            <XCircle className="w-3.5 h-3.5 text-slate-500" />
            Dismissed
          </span>
        );
      case 'ATTENDANCE_SUBMITTED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
            <FileText className="w-3.5 h-3.5 text-blue-600" />
            Attendance
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
            <Clock className="w-3.5 h-3.5 text-amber-600" />
            {action}
          </span>
        );
    }
  };

  const totalLogs = logs.length;
  const verifiedCount = logs.filter((l: AuditLog) => l.action.toUpperCase() === 'VERIFIED').length;
  const dismissedCount = logs.filter((l: AuditLog) => l.action.toUpperCase() === 'DISMISSED').length;

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
            <History className="w-6 h-6 text-gov-600 dark:text-gov-400" />
            Official Compliance Audit Trail
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Tamper-evident chronological record of all officer alert verifications, dismissals, and
            compliance reviews.
          </p>
        </div>

        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors shadow-sm self-start sm:self-auto"
        >
          <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin text-gov-600' : ''}`} />
          Refresh Trail
        </button>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm">
          <div className="text-xs font-medium text-slate-500 dark:text-slate-400">
            Total Logged Events
          </div>
          <div className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
            {totalLogs}
          </div>
        </div>
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm">
          <div className="text-xs font-medium text-emerald-600 dark:text-emerald-400">
            Verified Infractions
          </div>
          <div className="text-2xl font-bold text-emerald-700 dark:text-emerald-300 mt-1">
            {verifiedCount}
          </div>
        </div>
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm">
          <div className="text-xs font-medium text-slate-500 dark:text-slate-400">
            Dismissed False Positives
          </div>
          <div className="text-2xl font-bold text-slate-700 dark:text-slate-300 mt-1">
            {dismissedCount}
          </div>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm flex flex-col md:flex-row gap-4 items-center justify-between">
        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-600 dark:text-slate-400">
            <Filter className="w-4 h-4" />
            Filters:
          </div>

          {/* Centre Filter */}
          <select
            value={selectedCentre}
            onChange={(e) => setSelectedCentre(e.target.value)}
            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-medium focus:ring-2 focus:ring-gov-500"
          >
            <option value="">All Centres</option>
            {centres.map((c: Centre) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>

          {/* Action Filter */}
          <select
            value={selectedAction}
            onChange={(e) => setSelectedAction(e.target.value)}
            className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-medium focus:ring-2 focus:ring-gov-500"
          >
            <option value="">All Actions</option>
            <option value="VERIFIED">Verified</option>
            <option value="DISMISSED">Dismissed</option>
            <option value="ATTENDANCE_SUBMITTED">Attendance</option>
          </select>
        </div>

        {/* Officer Search */}
        <div className="relative w-full md:w-64">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search officer name..."
            value={officerFilter}
            onChange={(e) => setOfficerFilter(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs focus:ring-2 focus:ring-gov-500"
          />
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-sm">
        {isLoading ? (
          <div className="p-12 text-center text-sm text-slate-400 animate-pulse">
            Loading official audit records...
          </div>
        ) : logs.length === 0 ? (
          <div className="p-12 text-center space-y-2">
            <ShieldCheck className="w-8 h-8 text-slate-400 mx-auto" />
            <div className="text-sm font-semibold text-slate-700 dark:text-slate-300">
              No audit records found
            </div>
            <div className="text-xs text-slate-400">
              Actions taken by officers in the Alert Queue will appear here chronologically.
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 font-semibold border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="py-3 px-4">Timestamp (UTC)</th>
                  <th className="py-3 px-4">Officer / Reviewer</th>
                  <th className="py-3 px-4">Centre</th>
                  <th className="py-3 px-4">Alert ID</th>
                  <th className="py-3 px-4">Action</th>
                  <th className="py-3 px-4">Reviewer Notes & Rationale</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {logs.map((log: AuditLog) => (
                  <tr
                    key={log.id}
                    className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors"
                  >
                    <td className="py-3 px-4 whitespace-nowrap text-slate-600 dark:text-slate-400 font-mono">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-full bg-gov-100 dark:bg-gov-950 text-gov-700 dark:text-gov-300 flex items-center justify-center font-bold text-[10px]">
                          <UserCheck className="w-3.5 h-3.5" />
                        </div>
                        <span className="font-semibold text-slate-900 dark:text-white">
                          {log.officer_name}
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      <span className="inline-flex items-center gap-1 font-mono text-slate-700 dark:text-slate-300">
                        <Building className="w-3 h-3 text-slate-400" />
                        {log.centre_id}
                      </span>
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      {log.alert_id ? (
                        <span className="font-mono text-gov-600 dark:text-gov-400 font-semibold">
                          #{log.alert_id}
                        </span>
                      ) : (
                        <span className="text-slate-400">-</span>
                      )}
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      {getActionBadge(log.action)}
                    </td>
                    <td className="py-3 px-4 text-slate-700 dark:text-slate-300 max-w-md">
                      {log.notes || <span className="text-slate-400 italic">No notes provided</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

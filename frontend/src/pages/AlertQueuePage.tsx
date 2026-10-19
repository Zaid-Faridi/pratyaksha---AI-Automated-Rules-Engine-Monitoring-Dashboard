import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Filter, CheckCircle2, Search, ArrowRight, ShieldAlert } from 'lucide-react';
import { api } from '../api/client';
import { DataTable, Column } from '../components/common/DataTable';
import { SeverityBadge } from '../components/common/SeverityBadge';
import { StatusBadge } from '../components/common/StatusBadge';
import { AlertPanel } from '../components/alerts/AlertPanel';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { ErrorState } from '../components/common/ErrorState';
import { Alert, AlertReviewPayload } from '../types';

export const AlertQueuePage: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedCentre, setSelectedCentre] = useState<string>('all');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [selectedSeverity, setSelectedSeverity] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('open'); // Default to open alerts
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Fetch alerts with current filters
  const { data: alerts, isLoading, isError, refetch } = useQuery({
    queryKey: ['alerts', selectedCentre, selectedType, selectedSeverity, selectedStatus],
    queryFn: () =>
      api.getAlerts({
        centre_id: selectedCentre !== 'all' ? selectedCentre : undefined,
        type: selectedType !== 'all' ? selectedType : undefined,
        severity: selectedSeverity !== 'all' ? selectedSeverity : undefined,
        status: selectedStatus !== 'all' ? selectedStatus : undefined,
      }),
    refetchInterval: 30000,
  });

  // Fetch centres for dropdown
  const { data: centres } = useQuery({
    queryKey: ['centres'],
    queryFn: () => api.getCentres(),
  });

  // Optimistic review mutation
  const reviewMutation = useMutation({
    mutationFn: ({ alertId, payload }: { alertId: number; payload: AlertReviewPayload }) =>
      api.reviewAlert(alertId, payload),
    onMutate: async ({ alertId, payload }) => {
      await queryClient.cancelQueries({ queryKey: ['alerts'] });
      const previousAlerts = queryClient.getQueryData<Alert[]>(['alerts', selectedCentre, selectedType, selectedSeverity, selectedStatus]);

      // Optimistically update
      if (previousAlerts) {
        queryClient.setQueryData<Alert[]>(
          ['alerts', selectedCentre, selectedType, selectedSeverity, selectedStatus],
          previousAlerts.map((a) =>
            a.id === alertId
              ? {
                  ...a,
                  status: payload.status,
                  reviewed_by: payload.reviewed_by || 'Current User',
                  reviewed_at: new Date().toISOString(),
                  review_notes: payload.review_notes || a.review_notes,
                }
              : a
          )
        );
      }
      return { previousAlerts };
    },
    onError: (err, _, context) => {
      if (context?.previousAlerts) {
        queryClient.setQueryData(['alerts'], context.previousAlerts);
      }
      setToastMessage(`Failed to review alert: ${err.message}`);
      setTimeout(() => setToastMessage(null), 4000);
    },
    onSuccess: (updatedAlert) => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: ['dashboardSummary'] });
      setSelectedAlert(null);
      setToastMessage(`Alert #${updatedAlert.id} successfully updated to ${updatedAlert.status.toUpperCase()}.`);
      setTimeout(() => setToastMessage(null), 4000);
    },
  });

  const columns: Column<Alert>[] = [
    {
      header: 'ID & Type',
      accessor: 'type',
      sortable: true,
      render: (row) => (
        <div>
          <span className="font-bold text-slate-900 dark:text-slate-100 block">
            {row.type.replace(/_/g, ' ')}
          </span>
          <span className="text-[11px] text-slate-400 font-mono">#{row.id}</span>
        </div>
      ),
    },
    {
      header: 'Severity',
      accessor: 'severity',
      sortable: true,
      render: (row) => <SeverityBadge severity={row.severity} />,
    },
    {
      header: 'Centre ID',
      accessor: 'centre_id',
      sortable: true,
      render: (row) => (
        <span className="font-semibold text-slate-800 dark:text-slate-200">
          {row.centre_id}
        </span>
      ),
    },
    {
      header: 'Discrepancy Summary',
      render: (row) => (
        <p className="max-w-md truncate text-slate-600 dark:text-slate-300 font-medium">
          {row.message}
        </p>
      ),
    },
    {
      header: 'Timestamp',
      accessor: 'created_at',
      sortable: true,
      render: (row) => (
        <span className="text-slate-500 dark:text-slate-400">
          {new Date(row.created_at).toLocaleString([], {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          })}
        </span>
      ),
    },
    {
      header: 'Status',
      accessor: 'status',
      sortable: true,
      className: 'text-center',
      render: (row) => <StatusBadge status={row.status} />,
    },
    {
      header: 'Action',
      className: 'text-right',
      render: (row) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            setSelectedAlert(row);
          }}
          className="px-3 py-1 text-xs font-semibold rounded-lg bg-gov-50 dark:bg-gov-950 text-gov-600 dark:text-gov-400 hover:bg-gov-100 dark:hover:bg-gov-900 transition"
        >
          Review
        </button>
      ),
    },
  ];

  if (isLoading) {
    return (
      <div className="space-y-4">
        <LoadingSkeleton rows={1} className="h-14" />
        <LoadingSkeleton rows={8} className="h-14" />
      </div>
    );
  }

  if (isError) {
    return <ErrorState message="Could not fetch compliance alert records." onRetry={() => refetch()} />;
  }

  return (
    <div className="space-y-6 pb-10">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 px-4 py-2.5 rounded-lg bg-slate-900 text-white text-xs font-semibold shadow-xl border border-slate-700 animate-fade-in flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          {toastMessage}
        </div>
      )}

      {/* Page Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight flex items-center gap-2">
          <AlertTriangle className="w-6 h-6 text-amber-500" />
          Compliance Alert Queue
        </h1>
        <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
          Automated alerts flagged by rules engine for attendance shortfalls, equipment gaps, and camera health issues.
        </p>
      </div>

      {/* Multi-Dimensional Filter Bar */}
      <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 dark:text-slate-400">
          <Filter className="w-4 h-4 text-gov-600" />
          <span>Filters:</span>
        </div>

        {/* Centre Dropdown */}
        <select
          value={selectedCentre}
          onChange={(e) => setSelectedCentre(e.target.value)}
          className="text-xs py-1.5 px-3 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-800 dark:text-slate-200 focus:ring-2 focus:ring-gov-500 outline-none"
        >
          <option value="all">All Centres</option>
          {centres?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.id})
            </option>
          ))}
        </select>

        {/* Violation Type Dropdown */}
        <select
          value={selectedType}
          onChange={(e) => setSelectedType(e.target.value)}
          className="text-xs py-1.5 px-3 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-800 dark:text-slate-200 focus:ring-2 focus:ring-gov-500 outline-none"
        >
          <option value="all">All Violation Types</option>
          <option value="ATTENDANCE_MISMATCH">Attendance Mismatch</option>
          <option value="INSTRUCTOR_ABSENT">Instructor Absent from Podium</option>
          <option value="PPE_VIOLATION">PPE Compliance Violation</option>
          <option value="SAFETY_EQUIPMENT_MISSING">Safety Equipment Missing</option>
          <option value="MANDATORY_SIGNAGE_MISSING">Mandatory Signage Missing</option>
          <option value="CAPACITY_DEFICIT">Workstation Capacity Deficit</option>
          <option value="ZONE_IDLE_DURING_BATCH">Zone Inactivity / Idle</option>
          <option value="INFRASTRUCTURE_GAP">Infrastructure Gap</option>
          <option value="NON_FUNCTIONAL_EQUIPMENT">Non-Functional Equipment</option>
          <option value="POOR_CAMERA_QUALITY">Poor Camera Quality / Occluded</option>
          <option value="CAMERA_OFFLINE">Camera Offline</option>
          <option value="CAMERA_TAMPER">Camera Tampering</option>
          <option value="INFRASTRUCTURE_SURPLUS">Equipment Surplus (Info)</option>
        </select>

        {/* Severity Dropdown */}
        <select
          value={selectedSeverity}
          onChange={(e) => setSelectedSeverity(e.target.value)}
          className="text-xs py-1.5 px-3 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-800 dark:text-slate-200 focus:ring-2 focus:ring-gov-500 outline-none"
        >
          <option value="all">All Severities</option>
          <option value="CRITICAL">Critical</option>
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
          <option value="LOW">Low</option>
          <option value="INFO">Informational</option>
        </select>

        {/* Status Dropdown */}
        <select
          value={selectedStatus}
          onChange={(e) => setSelectedStatus(e.target.value)}
          className="text-xs py-1.5 px-3 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-800 dark:text-slate-200 focus:ring-2 focus:ring-gov-500 outline-none font-semibold text-gov-600 dark:text-gov-400"
        >
          <option value="open">Open Alerts Only</option>
          <option value="all">All Statuses (Open, Verified, Dismissed, Resolved)</option>
          <option value="verified">Verified</option>
          <option value="dismissed">Dismissed</option>
          <option value="auto_resolved">Auto-Resolved</option>
        </select>

        <span className="ml-auto text-xs font-medium text-slate-500 dark:text-slate-400">
          {alerts?.length || 0} alerts returned
        </span>
      </div>

      {/* Alerts DataTable */}
      <DataTable
        columns={columns}
        data={alerts || []}
        searchKey={(row) => `${row.message} ${row.centre_id} ${row.type}`}
        searchPlaceholder="Search alert message, centre ID, or type..."
        pageSize={10}
        onRowClick={(row) => setSelectedAlert(row)}
      />

      {/* Slide-over Detail Panel */}
      <AlertPanel
        alert={selectedAlert}
        onClose={() => setSelectedAlert(null)}
        onReview={async (alertId, payload) => {
          await reviewMutation.mutateAsync({ alertId, payload });
        }}
        isSubmitting={reviewMutation.isPending}
      />
    </div>
  );
};

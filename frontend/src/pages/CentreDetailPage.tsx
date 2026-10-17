import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  Building2,
  Calendar,
  Camera as CameraIcon,
  CheckCircle,
  Clock,
  Layers,
  Users,
  Video,
  VideoOff,
  AlertTriangle,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from 'recharts';

import { api } from '../api/client';
import { ScoreRing } from '../components/common/ScoreRing';
import { StatusBadge } from '../components/common/StatusBadge';
import { SeverityBadge } from '../components/common/SeverityBadge';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { ErrorState } from '../components/common/ErrorState';
import { AlertPanel } from '../components/alerts/AlertPanel';
import { Alert, AlertReviewPayload } from '../types';

export const CentreDetailPage: React.FC = () => {
  const { id = '' } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // 1. Fetch Centre info
  const { data: centre, isLoading: loadingCentre } = useQuery({
    queryKey: ['centre', id],
    queryFn: () => api.getCentre(id),
  });

  // 2. Fetch Compliance Breakdown
  const { data: compliance, isLoading: loadingComp } = useQuery({
    queryKey: ['centreCompliance', id],
    queryFn: () => api.getCentreCompliance(id),
  });

  // 3. Fetch Attendance History (Claimed vs Detected)
  const { data: attendanceHistory, isLoading: loadingAtt } = useQuery({
    queryKey: ['centreAttendanceHistory', id],
    queryFn: () => api.getCentreAttendanceHistory(id),
  });

  // 4. Fetch Infrastructure Status per zone
  const { data: infraStatus, isLoading: loadingInfra } = useQuery({
    queryKey: ['centreInfrastructureStatus', id],
    queryFn: () => api.getCentreInfrastructureStatus(id),
  });

  // 5. Fetch Cameras
  const { data: cameras, isLoading: loadingCams } = useQuery({
    queryKey: ['centreCameras', id],
    queryFn: () => api.getCameras(id),
  });

  // 6. Fetch Alerts for this centre
  const { data: alerts, isLoading: loadingAlerts } = useQuery({
    queryKey: ['centreAlerts', id],
    queryFn: () => api.getAlerts({ centre_id: id }),
  });

  // Review mutation
  const reviewMutation = useMutation({
    mutationFn: ({ alertId, payload }: { alertId: number; payload: AlertReviewPayload }) =>
      api.reviewAlert(alertId, payload),
    onSuccess: (updatedAlert) => {
      queryClient.invalidateQueries({ queryKey: ['centreAlerts', id] });
      queryClient.invalidateQueries({ queryKey: ['dashboardSummary'] });
      setSelectedAlert(null);
      setToastMessage(`Alert #${updatedAlert.id} marked as ${updatedAlert.status}.`);
      setTimeout(() => setToastMessage(null), 4000);
    },
    onError: (err) => {
      setToastMessage(`Error updating alert: ${err.message}`);
      setTimeout(() => setToastMessage(null), 4000);
    },
  });

  if (loadingCentre || loadingComp) {
    return (
      <div className="space-y-6">
        <LoadingSkeleton rows={1} className="h-10 w-48" />
        <LoadingSkeleton rows={1} className="h-44" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <LoadingSkeleton rows={1} className="h-80" />
          <LoadingSkeleton rows={1} className="h-80" />
        </div>
      </div>
    );
  }

  if (!centre) {
    return <ErrorState message={`Skilling centre '${id}' could not be located.`} />;
  }

  const score = compliance?.compliance_score ?? 0;

  return (
    <div className="space-y-7 pb-12">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 px-4 py-2.5 rounded-lg bg-slate-900 text-white text-xs font-semibold shadow-xl border border-slate-700 animate-fade-in flex items-center gap-2">
          <CheckCircle className="w-4 h-4 text-emerald-400" />
          {toastMessage}
        </div>
      )}

      {/* Back button & Breadcrumb */}
      <div>
        <Link
          to="/centres"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 transition"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Centres Directory
        </Link>
      </div>

      {/* Header Banner with Score & Breakdown */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm p-6 sm:p-7">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          {/* Centre Basic Details */}
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="text-xs font-bold px-2.5 py-0.5 rounded bg-gov-100 text-gov-800 dark:bg-gov-950 dark:text-gov-300 border border-gov-200 dark:border-gov-800">
                {centre.scheme}
              </span>
              <StatusBadge status={compliance?.summary_status || 'COMPLIANT'} />
              <span className="text-xs text-slate-400 font-mono">ID: {centre.id}</span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-slate-50 tracking-tight">
              {centre.name}
            </h1>
            <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400">
              {centre.district}, {centre.state} • GPS: {centre.lat.toFixed(4)}° N, {centre.lng.toFixed(4)}° E
            </p>
          </div>

          {/* Primary Score Ring and Breakdown Meters */}
          <div className="flex items-center gap-6 p-4 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200/80 dark:border-slate-800">
            <ScoreRing score={score} size="lg" />

            <div className="space-y-2 text-xs">
              <div className="text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                Compliance Breakdown
              </div>

              {/* Attendance Match */}
              <div className="w-44 sm:w-52">
                <div className="flex justify-between font-semibold mb-0.5">
                  <span className="text-slate-700 dark:text-slate-300">Attendance Match (45%)</span>
                  <span className={compliance && compliance.attendance_rate < 0.70 ? 'text-rose-600' : 'text-slate-900 dark:text-slate-100'}>
                    {((compliance?.attendance_rate ?? 1.0) * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="w-full bg-slate-200 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
                  <div
                    className="bg-gov-600 h-full rounded-full"
                    style={{ width: `${Math.min(100, (compliance?.attendance_rate ?? 1) * 100)}%` }}
                  />
                </div>
              </div>

              {/* Infrastructure Availability */}
              <div className="w-44 sm:w-52">
                <div className="flex justify-between font-semibold mb-0.5">
                  <span className="text-slate-700 dark:text-slate-300">Infra Availability (35%)</span>
                  <span>{((compliance?.infrastructure_availability_rate ?? 1.0) * 100).toFixed(0)}%</span>
                </div>
                <div className="w-full bg-slate-200 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
                  <div
                    className="bg-teal-600 h-full rounded-full"
                    style={{ width: `${Math.min(100, (compliance?.infrastructure_availability_rate ?? 1) * 100)}%` }}
                  />
                </div>
              </div>

              {/* Camera Uptime */}
              <div className="w-44 sm:w-52">
                <div className="flex justify-between font-semibold mb-0.5">
                  <span className="text-slate-700 dark:text-slate-300">Camera Uptime (20%)</span>
                  <span>{((compliance?.camera_uptime_rate ?? 1.0) * 100).toFixed(0)}%</span>
                </div>
                <div className="w-full bg-slate-200 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
                  <div
                    className="bg-emerald-600 h-full rounded-full"
                    style={{ width: `${Math.min(100, (compliance?.camera_uptime_rate ?? 1) * 100)}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Grid: Attendance Chart & Zone Infrastructure Table */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Attendance Chart (User Requirement: Claimed vs Detected per batch/day with mismatch highlight) */}
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm p-5 flex flex-col justify-between">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                <Users className="w-4 h-4 text-gov-600" />
                Attendance Verification: Claimed vs Observed
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Observed rolling median person count vs claimed submissions per batch
              </p>
            </div>
          </div>

          <div className="h-64 w-full">
            {attendanceHistory && attendanceHistory.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={attendanceHistory} margin={{ top: 15, right: 15, left: -15, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0F172A',
                      borderColor: '#334155',
                      borderRadius: '8px',
                      color: '#F8FAFC',
                      fontSize: '12px',
                    }}
                    formatter={(val: number, name: string) => [val, name === 'claimed_count' ? 'Official Claimed' : 'AI Observed']}
                  />
                  <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                  <Bar dataKey="claimed_count" name="Claimed Attendance" fill="#94A3B8" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="detected_count" name="Observed Count" fill="#0284C7" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-slate-400">
                No attendance events logged yet for this centre.
              </div>
            )}
          </div>

          {/* Mismatch indicator notes */}
          {attendanceHistory?.some((h) => h.mismatch) && (
            <div className="mt-3 p-2.5 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-xs text-rose-700 dark:text-rose-300 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0 text-rose-600" />
              <span>
                <strong>Attendance Mismatch Alert Triggered:</strong> Actual attendance fell below 70% of claimed count across consecutive sampling windows.
              </span>
            </div>
          )}
        </div>

        {/* Zone Infrastructure Compliance Table */}
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm p-5 flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5 mb-1">
              <Layers className="w-4 h-4 text-teal-600" />
              Sanctioned Equipment Inventory by Zone
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
              Real-time audit comparing computer, workbench, and chair counts
            </p>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 font-semibold uppercase tracking-wider">
                    <th className="p-2.5">Zone ROI</th>
                    <th className="p-2.5">Item Name</th>
                    <th className="p-2.5 text-center">Sanctioned</th>
                    <th className="p-2.5 text-center">Detected</th>
                    <th className="p-2.5 text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/70">
                  {infraStatus && infraStatus.length > 0 ? (
                    infraStatus.map((row, idx) => (
                      <tr key={idx} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/30">
                        <td className="p-2.5 font-medium text-slate-800 dark:text-slate-200">{row.zone}</td>
                        <td className="p-2.5 capitalize font-medium">{row.item}</td>
                        <td className="p-2.5 text-center font-bold text-slate-600 dark:text-slate-300">{row.expected}</td>
                        <td className="p-2.5 text-center font-bold">{row.detected}</td>
                        <td className="p-2.5 text-right">
                          <StatusBadge status={row.status} />
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={5} className="p-6 text-center text-slate-400">
                        No sanctioned inventory items defined for this centre.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* Camera Health Panel */}
      <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm p-5">
        <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5 mb-1">
          <CameraIcon className="w-4 h-4 text-gov-600" />
          Camera Feeds & Health Heartbeats
        </h3>
        <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
          Edge camera connection telemetry and active zones
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {cameras && cameras.length > 0 ? (
            cameras.map((cam) => (
              <div
                key={cam.id}
                className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-xs text-slate-900 dark:text-slate-100 font-mono">
                      {cam.id}
                    </span>
                    <StatusBadge status={cam.status.toUpperCase()} />
                  </div>
                  <div className="text-xs text-slate-500 dark:text-slate-400 space-y-1 mb-3">
                    <p>
                      <span className="font-medium text-slate-700 dark:text-slate-300">Zones:</span>{' '}
                      {cam.zone_names?.join(', ') || 'Global'}
                    </p>
                    {cam.rtsp_url && (
                      <p className="truncate text-[11px] font-mono text-slate-400">
                        {cam.rtsp_url}
                      </p>
                    )}
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-200 dark:border-slate-800 text-[11px] text-slate-500 flex items-center justify-between">
                  <span>Last Seen:</span>
                  <span className="font-medium text-slate-700 dark:text-slate-300">
                    {cam.last_seen_at ? new Date(cam.last_seen_at).toLocaleTimeString() : 'Never'}
                  </span>
                </div>
              </div>
            ))
          ) : (
            <div className="col-span-full p-4 text-center text-xs text-slate-400">
              No cameras registered for this centre.
            </div>
          )}
        </div>
      </div>

      {/* Recent Alerts for this Centre */}
      <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
        <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-amber-500" />
              Compliance Alerts Log
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Historical and active violations flagged by the rules engine
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 font-semibold uppercase tracking-wider">
                <th className="p-3">Type</th>
                <th className="p-3">Severity</th>
                <th className="p-3">Violation Details</th>
                <th className="p-3">Triggered</th>
                <th className="p-3 text-center">Status</th>
                <th className="p-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/70">
              {alerts && alerts.length > 0 ? (
                alerts.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/30">
                    <td className="p-3 font-semibold text-slate-800 dark:text-slate-200">
                      {a.type.replace(/_/g, ' ')}
                    </td>
                    <td className="p-3">
                      <SeverityBadge severity={a.severity} />
                    </td>
                    <td className="p-3 max-w-md text-slate-600 dark:text-slate-300 truncate">
                      {a.message}
                    </td>
                    <td className="p-3 text-slate-400">
                      {new Date(a.created_at).toLocaleDateString()} {new Date(a.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </td>
                    <td className="p-3 text-center">
                      <StatusBadge status={a.status} />
                    </td>
                    <td className="p-3 text-right">
                      <button
                        onClick={() => setSelectedAlert(a)}
                        className="px-2.5 py-1 text-xs font-semibold rounded bg-gov-50 dark:bg-gov-950 text-gov-600 dark:text-gov-400 hover:bg-gov-100 dark:hover:bg-gov-900 transition"
                      >
                        Review
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="p-6 text-center text-xs text-slate-400">
                    No compliance alerts recorded for this centre.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Alert Review Slide-over Panel */}
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

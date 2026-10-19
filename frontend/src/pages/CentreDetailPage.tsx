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
  Wrench,
  ShieldCheck,
  HardHat,
  Flame,
  Activity,
  Edit3,
  X,
  Save,
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
  const [isTradeModalOpen, setIsTradeModalOpen] = useState(false);
  const [selectedTradeId, setSelectedTradeId] = useState<string>('');
  const [overridesJson, setOverridesJson] = useState<string>('{}');

  // 1. Fetch Centre info
  const { data: centre, isLoading: loadingCentre } = useQuery({
    queryKey: ['centre', id],
    queryFn: () => api.getCentre(id),
  });

  // 1b. Fetch Effective Trade Profile for this Centre
  const { data: effectiveTrade, isLoading: loadingTrade } = useQuery({
    queryKey: ['centreEffectiveTrade', id],
    queryFn: async () => {
      const data = await api.getCentreEffectiveTrade(id);
      if (data?.trade_id) {
        setSelectedTradeId(data.trade_id);
      }
      if (data?.overrides) {
        setOverridesJson(JSON.stringify(data.overrides, null, 2));
      }
      return data;
    },
  });

  // 1c. Fetch All Master Trades for dropdown
  const { data: allTrades } = useQuery({
    queryKey: ['allTrades'],
    queryFn: () => api.getTrades(),
  });

  // Trade override mutation
  const updateTradeMutation = useMutation({
    mutationFn: (payload: { trade_id: string; trade_overrides: any }) =>
      api.updateCentreTradeOverrides(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['centreEffectiveTrade', id] });
      queryClient.invalidateQueries({ queryKey: ['centre', id] });
      queryClient.invalidateQueries({ queryKey: ['centreInfrastructureStatus', id] });
      setIsTradeModalOpen(false);
      setToastMessage('Trade profile and zone-level standards updated successfully.');
      setTimeout(() => setToastMessage(null), 4000);
    },
    onError: (err: any) => {
      setToastMessage(`Error updating trade profile: ${err.message}`);
      setTimeout(() => setToastMessage(null), 4000);
    },
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

      {/* Back button & Breadcrumb & Report Exports */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <Link
          to="/centres"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 transition"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Centres Directory
        </Link>

        <div className="flex items-center gap-2">
          <a
            href={api.getReportCsvUrl(id)}
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 transition shadow-sm"
          >
            Export Centre CSV
          </a>
          <a
            href={api.getReportPdfUrl(id)}
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-gov-600 hover:bg-gov-700 text-white transition shadow-sm"
          >
            Official Centre PDF
          </a>
        </div>
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

      {/* Master Vocational Trade Profile & Standards Card */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-slate-100 dark:border-slate-800">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="p-1.5 rounded-lg bg-teal-50 dark:bg-teal-950/60 text-teal-600 dark:text-teal-400">
                <Wrench className="w-5 h-5" />
              </span>
              <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
                Vocational Trade Profile: {effectiveTrade?.name || 'General Skilling'}
              </h2>
              <span className="text-xs px-2.5 py-0.5 rounded-full font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                {effectiveTrade?.category || 'Standard SSC Curriculum'}
              </span>
              {effectiveTrade?.overrides && Object.keys(effectiveTrade.overrides).length > 0 && (
                <span className="text-[10px] px-2 py-0.5 rounded font-bold bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
                  Zone Overrides Active
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 max-w-3xl">
              {effectiveTrade?.description || 'Defines sanctioned equipment norms, open-vocabulary detector prompts, and automated operability checks for this centre.'}
            </p>
          </div>

          <button
            onClick={() => {
              setSelectedTradeId(effectiveTrade?.trade_id || 'it_lab');
              setOverridesJson(JSON.stringify(effectiveTrade?.overrides || {}, null, 2));
              setIsTradeModalOpen(true);
            }}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 transition self-start sm:self-center"
          >
            <Edit3 className="w-3.5 h-3.5 text-slate-500" />
            Edit Profile & Overrides
          </button>
        </div>

        {/* 3-Column Standards Summary */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mt-5">
          {/* Column 1: Required PPE */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200/80 dark:border-slate-800">
            <div className="flex items-center gap-2 mb-2 text-xs font-bold text-slate-800 dark:text-slate-200">
              <HardHat className="w-4 h-4 text-amber-500" />
              <span>Mandatory PPE (Zero-PII Aggregate)</span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 mb-3">
              Minimum {effectiveTrade?.compliance_checks?.ppe_compliance?.min_compliance_ratio ? Math.round(effectiveTrade.compliance_checks.ppe_compliance.min_compliance_ratio * 100) : 80}% aggregate compliance required
            </p>
            <div className="flex flex-wrap gap-1.5">
              {effectiveTrade?.required_ppe && effectiveTrade.required_ppe.length > 0 ? (
                effectiveTrade.required_ppe.map((item: string, idx: number) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-100 dark:bg-amber-950/60 text-amber-900 dark:text-amber-300 border border-amber-200 dark:border-amber-900 capitalize"
                  >
                    {item.replace(/_/g, ' ')}
                  </span>
                ))
              ) : (
                <span className="text-xs text-slate-400 italic">Standard uniform / general dress code</span>
              )}
            </div>
          </div>

          {/* Column 2: Safety & Entrance Items */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200/80 dark:border-slate-800">
            <div className="flex items-center gap-2 mb-2 text-xs font-bold text-slate-800 dark:text-slate-200">
              <ShieldCheck className="w-4 h-4 text-emerald-500" />
              <span>Safety & Entrance Compliance</span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 mb-3">
              Verified continuously via entrance and workshop ROI feeds
            </p>
            <div className="flex flex-wrap gap-1.5">
              {(effectiveTrade?.safety_items || ['fire_extinguisher', 'first_aid_box']).map((item: string, idx: number) => (
                <span
                  key={idx}
                  className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-100 dark:bg-emerald-950/60 text-emerald-900 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-900 capitalize"
                >
                  {item.replace(/_/g, ' ')}
                </span>
              ))}
              {(effectiveTrade?.mandatory_signage || ['safety_signage', 'biometric_device']).map((item: string, idx: number) => (
                <span
                  key={`sign-${idx}`}
                  className="px-2 py-0.5 rounded text-[11px] font-semibold bg-cyan-100 dark:bg-cyan-950/60 text-cyan-900 dark:text-cyan-300 border border-cyan-200 dark:border-cyan-900 capitalize"
                >
                  {item.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          </div>

          {/* Column 3: Workstation Capacity & Activity State */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200/80 dark:border-slate-800">
            <div className="flex items-center gap-2 mb-2 text-xs font-bold text-slate-800 dark:text-slate-200">
              <Activity className="w-4 h-4 text-gov-600" />
              <span>Capacity & Session Activity</span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 mb-2">
              Workstation ratio: {effectiveTrade?.workstation_capacity_rule?.min_stations_per_candidate || 1.0} per batch student
            </p>
            <div className="text-xs space-y-1 text-slate-600 dark:text-slate-300">
              <div className="flex justify-between">
                <span>Instructor Zone Rule:</span>
                <span className="font-semibold text-slate-900 dark:text-slate-100">
                  {effectiveTrade?.compliance_checks?.instructor_presence?.enabled ? 'Active (Podium ROI)' : 'Disabled'}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Activity State Detection:</span>
                <span className="font-semibold text-slate-900 dark:text-slate-100">Active / Idle / Empty</span>
              </div>
            </div>
          </div>
        </div>

        {/* Detailed Sanctioned Equipment Norms Table */}
        <div className="mt-5 overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 font-semibold uppercase tracking-wider">
                <th className="p-2.5">Sanctioned Item</th>
                <th className="p-2.5 text-center">Norm Quota</th>
                <th className="p-2.5">Open-Vocabulary Detector Prompt</th>
                <th className="p-2.5">Operability CV Heuristic</th>
                <th className="p-2.5">Equipment Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/70">
              {effectiveTrade?.sanctioned_equipment && effectiveTrade.sanctioned_equipment.length > 0 ? (
                effectiveTrade.sanctioned_equipment.map((eq: any, idx: number) => (
                  <tr key={idx} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/30">
                    <td className="p-2.5 font-bold capitalize text-slate-900 dark:text-slate-100">{eq.item}</td>
                    <td className="p-2.5 text-center font-bold text-gov-600 dark:text-gov-400">{eq.expected_per_zone}</td>
                    <td className="p-2.5 font-mono text-[11px] text-slate-600 dark:text-slate-300 max-w-xs truncate">{eq.detector_prompt}</td>
                    <td className="p-2.5">
                      <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                        {eq.operability_heuristic}
                      </span>
                    </td>
                    <td className="p-2.5 text-slate-500 dark:text-slate-400 text-[11px]">{eq.description}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="p-4 text-center text-slate-400">
                    Loading trade equipment profile...
                  </td>
                </tr>
              )}
            </tbody>
          </table>
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
                    <th className="p-2.5 text-center">Operability</th>
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
                        <td className="p-2.5 text-center">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold ${
                              row.operability === 'non_operational'
                                ? 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                                : row.operability === 'uncertain'
                                ? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                                : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                            }`}
                          >
                            {row.operability || 'operational'}
                          </span>
                        </td>
                        <td className="p-2.5 text-right">
                          <StatusBadge status={row.status} />
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} className="p-6 text-center text-slate-400">
                        No sanctioned inventory items defined for this centre.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <p className="text-[10px] text-slate-400 italic mt-3 pt-2 border-t border-slate-100 dark:border-slate-800">
              * Operability is a heuristic indication based on computer vision signals (active screen illumination, power LED regions, tool interaction, and unobstructed seating). Not an electrical or mechanical diagnostic.
            </p>
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
                    <div className="flex items-center gap-1.5">
                      <span className="font-bold text-xs text-slate-900 dark:text-slate-100 font-mono">
                        {cam.id}
                      </span>
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                        Quality: Reliable
                      </span>
                    </div>
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

      {/* Trade Profile & Zone Overrides Configuration Modal */}
      {isTradeModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-xl rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xl p-6 space-y-5 animate-scale-in">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <span className="p-1.5 rounded-lg bg-teal-50 dark:bg-teal-950/60 text-teal-600 dark:text-teal-400">
                  <Wrench className="w-5 h-5" />
                </span>
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                  Configure Centre Trade Profile & Overrides
                </h3>
              </div>
              <button
                onClick={() => setIsTradeModalOpen(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                  Select Master Trade Profile (SSC Standard)
                </label>
                <select
                  value={selectedTradeId}
                  onChange={(e) => setSelectedTradeId(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 font-semibold focus:outline-none focus:ring-2 focus:ring-teal-500"
                >
                  {allTrades && allTrades.length > 0 ? (
                    allTrades.map((t: any) => (
                      <option key={t.id} value={t.id}>
                        {t.name} ({t.category})
                      </option>
                    ))
                  ) : (
                    <option value="it_lab">IT & Computer Lab Training</option>
                  )}
                </select>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                  Defines baseline equipment quotas, prompt detectors, and required PPE for {centre.name}.
                </p>
              </div>

              <div>
                <label className="block font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                  Zone-Level Overrides & Custom Quotas (JSON)
                </label>
                <textarea
                  rows={8}
                  value={overridesJson}
                  onChange={(e) => setOverridesJson(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 font-mono text-[11px] text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
                  placeholder='{"sanctioned_equipment": [...], "required_ppe": [...]}'
                />
                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                  Allows customizing specific equipment counts, adding custom tools, or modifying compliance thresholds for this centre.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100 dark:border-slate-800">
              <button
                type="button"
                onClick={() => setIsTradeModalOpen(false)}
                className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={updateTradeMutation.isPending}
                onClick={() => {
                  try {
                    const parsedOverrides = JSON.parse(overridesJson || '{}');
                    updateTradeMutation.mutate({
                      trade_id: selectedTradeId,
                      trade_overrides: parsedOverrides,
                    });
                  } catch (err: any) {
                    alert(`Invalid JSON format in overrides: ${err.message}`);
                  }
                }}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold bg-teal-600 hover:bg-teal-700 text-white transition disabled:opacity-50 shadow-sm"
              >
                <Save className="w-4 h-4" />
                {updateTradeMutation.isPending ? 'Saving Standards...' : 'Save Configuration'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

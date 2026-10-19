import React, { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Radio,
  Video,
  ShieldCheck,
  AlertTriangle,
  Users,
  Wrench,
  RefreshCw,
  LayoutGrid,
  CheckCircle2,
  XCircle,
  Wifi,
  WifiOff,
  Sliders,
  Maximize2,
  Camera as CameraIcon,
  EyeOff,
  Play,
  Pause,
  Layers,
  Flame,
  ShieldAlert,
  UserCheck,
  Activity,
  Briefcase,
  ExternalLink,
  Sparkles,
  HardHat,
} from 'lucide-react';

import { api } from '../api/client';
import { Camera, Centre, LiveTelemetryPayload, LiveAlertTickerItem } from '../types';

export const LiveMonitorPage: React.FC = () => {
  // View Mode: Single Camera Feed vs 4-Centre Multi-Centre Wall View
  const [viewMode, setViewMode] = useState<'single' | 'wall'>('single');
  const [activeScenario, setActiveScenario] = useState<string>('compliant');

  // Queries for Centres and Cameras
  const { data: centres = [] } = useQuery({
    queryKey: ['centres'],
    queryFn: () => api.getCentres(),
  });

  const { data: cameras = [], refetch: refetchCameras } = useQuery({
    queryKey: ['cameras'],
    queryFn: () => api.getCameras(),
  });

  // Query 4-Centre Wall View Metadata
  const { data: wallData, refetch: refetchWall } = useQuery({
    queryKey: ['streaming-wall'],
    queryFn: () => api.getMultiCentreWall(),
    refetchInterval: 4000,
  });

  // Query Demo Footage Manifest
  const { data: manifestData } = useQuery({
    queryKey: ['streaming-manifest'],
    queryFn: () => api.getStreamingManifest(),
  });

  // Selected State
  const [selectedCentreId, setSelectedCentreId] = useState<string>('');
  const [selectedCameraId, setSelectedCameraId] = useState<string>('');
  const [gridLayout, setGridLayout] = useState<'1' | '2' | '4'>('1');

  // Stream Mode vs Snapshot Mode
  const [isSnapshotMode, setIsSnapshotMode] = useState<boolean>(false);
  const [snapshotTimestamp, setSnapshotTimestamp] = useState<number>(Date.now());
  const [isDemoMode, setIsDemoMode] = useState<boolean>(true);
  const [claimedAttendance, setClaimedAttendance] = useState<number>(18);

  // Connection & Stream State
  const [streamLoading, setStreamLoading] = useState<boolean>(true);
  const [streamError, setStreamError] = useState<boolean>(false);
  const [reconnectKey, setReconnectKey] = useState<number>(1);
  const [reconnectAttempts, setReconnectAttempts] = useState<number>(0);

  // Live Telemetry State (populated via SSE or polling)
  const [telemetry, setTelemetry] = useState<LiveTelemetryPayload | null>(null);
  const [liveAlerts, setLiveAlerts] = useState<LiveAlertTickerItem[]>([]);
  const sseRef = useRef<EventSource | null>(null);

  // Auto-select first centre and camera when data loads
  useEffect(() => {
    if (centres.length > 0 && !selectedCentreId) {
      setSelectedCentreId(centres[0].id);
    }
  }, [centres, selectedCentreId]);

  const centreCameras = cameras.filter((c) => !selectedCentreId || c.centre_id === selectedCentreId);
  const activeCentre = centres.find((c) => c.id === selectedCentreId);

  useEffect(() => {
    if (centreCameras.length > 0) {
      if (!selectedCameraId || !centreCameras.some((c) => c.id === selectedCameraId)) {
        setSelectedCameraId(centreCameras[0].id);
      }
    }
  }, [centreCameras, selectedCameraId]);

  const activeCamera = cameras.find((c) => c.id === selectedCameraId) || centreCameras[0];

  // SSE Telemetry Connection
  useEffect(() => {
    if (!activeCamera) return;

    // Close previous SSE if any
    if (sseRef.current) {
      sseRef.current.close();
      sseRef.current = null;
    }

    const telemetryUrl = api.getCameraTelemetryUrl(activeCamera.id);
    try {
      const es = new EventSource(telemetryUrl);
      sseRef.current = es;

      es.onmessage = (event) => {
        try {
          const data: LiveTelemetryPayload = JSON.parse(event.data);
          setTelemetry(data);
          if (data.recent_alerts && data.recent_alerts.length > 0) {
            setLiveAlerts((prev) => {
              const newAlerts = [...data.recent_alerts];
              const seenIds = new Set(newAlerts.map((a) => a.id));
              const filteredPrev = prev.filter((a) => !seenIds.has(a.id));
              return [...newAlerts, ...filteredPrev].slice(0, 15);
            });
          }
        } catch {
          // ignore malformed SSE
        }
      };

      es.onerror = () => {
        // Fallback: fetch status via REST if SSE drops
        api.getCameraLiveStatus(activeCamera.id).then((status) => {
          if (status?.latest_telemetry) {
            setTelemetry(status.latest_telemetry);
          }
        }).catch(() => {});
      };
    } catch {
      // EventSource not supported or blocked
    }

    return () => {
      if (sseRef.current) {
        sseRef.current.close();
        sseRef.current = null;
      }
    };
  }, [activeCamera?.id]);

  // Snapshot Mode interval timer (every 7 seconds)
  useEffect(() => {
    if (!isSnapshotMode) return;
    const interval = setInterval(() => {
      setSnapshotTimestamp(Date.now());
    }, 7000);
    return () => clearInterval(interval);
  }, [isSnapshotMode]);

  // Reset stream loading on camera switch
  useEffect(() => {
    setStreamLoading(true);
    setStreamError(false);
    setReconnectAttempts(0);
    setReconnectKey((k) => k + 1);
  }, [selectedCameraId, isSnapshotMode]);

  const handleStreamError = () => {
    setStreamLoading(false);
    setStreamError(true);
    // Auto-reconnect up to 4 attempts with exponential backoff
    if (reconnectAttempts < 4) {
      const delay = Math.min(6000, 1500 * Math.pow(1.5, reconnectAttempts));
      setReconnectAttempts((a) => a + 1);
      setTimeout(() => {
        setReconnectKey((k) => k + 1);
        setStreamError(false);
      }, delay);
    }
  };

  const handleManualReconnect = () => {
    setStreamError(false);
    setStreamLoading(true);
    setReconnectAttempts(0);
    setReconnectKey((k) => k + 1);
  };

  const handleUpdateClaimedQuota = async (newQuota: number) => {
    setClaimedAttendance(newQuota);
    if (activeCamera) {
      try {
        await api.updateDemoConfig(activeCamera.id, { claimed_attendance: newQuota });
      } catch (err) {
        console.warn('Failed to update live claimed quota', err);
      }
    }
  };

  const handleToggleStreamingPolicy = async () => {
    if (!activeCentre) return;
    const newPolicy = !(activeCentre.live_streaming_enabled ?? true);
    try {
      await api.toggleCentreStreaming(activeCentre.id, newPolicy);
      activeCentre.live_streaming_enabled = newPolicy;
      refetchCameras();
      setReconnectKey((k) => k + 1);
    } catch (err) {
      alert('Failed to update centre streaming policy: ' + err);
    }
  };

  const handleScenarioChange = async (newScenario: string, camId?: string) => {
    const targetCamId = camId || activeCamera?.id;
    if (!targetCamId) return;
    if (!camId) setActiveScenario(newScenario);
    try {
      await api.updateDemoConfig(targetCamId, { scenario: newScenario });
      setReconnectKey((k) => k + 1);
      refetchWall();
    } catch (err) {
      console.warn('Failed to update live demo scenario', err);
    }
  };

  // Derive active attendance calculation
  const classroomTelemetry = telemetry?.zones?.classroom;
  const detectedHeadcount = classroomTelemetry?.smoothed_count ?? (telemetry?.total_persons_detected ?? 5);
  const activeClaimed = classroomTelemetry?.claimed_attendance ?? claimedAttendance;
  const attendanceRatio = activeClaimed > 0 ? detectedHeadcount / activeClaimed : 1.0;
  const attendancePercent = Math.min(100, Math.round(attendanceRatio * 100));
  const isMismatch = activeClaimed > 0 && attendanceRatio < 0.70;

  // Stream URL calculation
  const streamUrl = activeCamera
    ? isSnapshotMode
      ? api.getCameraSnapshotUrl(activeCamera.id) + `&key=${reconnectKey}&ts=${snapshotTimestamp}`
      : api.getCameraStreamUrl(activeCamera.id, { claimedAttendance, demo: isDemoMode, scenario: activeScenario }) + `&key=${reconnectKey}`
    : '';

  const isStreamingForbidden = activeCentre && activeCentre.live_streaming_enabled === false;
  const isCameraOffline = activeCamera?.status === 'offline';

  return (
    <div className="space-y-6 pb-12">
      {/* Top Header & Overview */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight">
              Live Video Analytics Monitor
            </h1>
            <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-100 dark:bg-rose-950/70 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-900">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500"></span>
              </span>
              ON-DEMAND STREAM
            </span>
          </div>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
            Edge-rendered live feeds with privacy blurring, automated zone counting, and multi-trade compliance auditing.
          </p>
        </div>

        {/* Global Controls: View Mode & Snapshot Mode */}
        <div className="flex flex-wrap items-center gap-2">
          {/* View Mode Toggle: Single Camera vs 4-Centre Multi-Centre Wall View */}
          <div className="inline-flex rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-0.5 shadow-sm text-xs font-semibold">
            <button
              onClick={() => setViewMode('single')}
              className={`px-3 py-1.5 rounded-md flex items-center gap-1.5 transition ${
                viewMode === 'single'
                  ? 'bg-gov-600 text-white shadow-sm'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
              }`}
            >
              <Video className="w-3.5 h-3.5" />
              <span>Single Camera</span>
            </button>
            <button
              onClick={() => setViewMode('wall')}
              className={`px-3 py-1.5 rounded-md flex items-center gap-1.5 transition ${
                viewMode === 'wall'
                  ? 'bg-gov-600 text-white shadow-sm'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
              }`}
            >
              <LayoutGrid className="w-3.5 h-3.5 text-teal-400" />
              <span>4-Centre Wall View</span>
            </button>
          </div>

          {/* Low Bandwidth Snapshot Mode Toggle */}
          <button
            onClick={() => setIsSnapshotMode(!isSnapshotMode)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 border transition ${
              isSnapshotMode
                ? 'bg-amber-100 dark:bg-amber-950/70 text-amber-800 dark:text-amber-200 border-amber-300 dark:border-amber-800 shadow-sm'
                : 'bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800'
            }`}
            title="Switch to periodic snapshot mode to conserve rural bandwidth (5-10s refresh)"
          >
            <CameraIcon className="w-3.5 h-3.5" />
            <span>{isSnapshotMode ? 'Snapshot Mode (7s)' : 'Live Stream (7 FPS)'}</span>
          </button>
        </div>
      </div>

      {/* Selectors Bar & Centre Policy Banner */}
      <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 items-center">
          {/* Centre Dropdown */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">
              Skilling Centre
            </label>
            <select
              value={selectedCentreId}
              onChange={(e) => setSelectedCentreId(e.target.value)}
              className="w-full text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-gov-500"
            >
              {centres.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.state})
                </option>
              ))}
            </select>
          </div>

          {/* Camera Dropdown */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">
              Select Camera Feed
            </label>
            <select
              value={selectedCameraId}
              onChange={(e) => setSelectedCameraId(e.target.value)}
              className="w-full text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-gov-500"
            >
              {centreCameras.map((cam) => (
                <option key={cam.id} value={cam.id}>
                  {cam.id} — Zones: {cam.zone_names?.join(', ') || 'Classroom/Workshop'} ({cam.status})
                </option>
              ))}
            </select>
          </div>

          {/* Demo Scenario Injection Dropdown */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-amber-500" />
              <span>Demo Scenario</span>
            </label>
            <select
              value={activeScenario}
              onChange={(e) => handleScenarioChange(e.target.value)}
              className="w-full text-xs rounded-lg border border-amber-300 dark:border-amber-700/60 bg-amber-50/50 dark:bg-amber-950/20 px-3 py-2 text-slate-900 dark:text-slate-100 font-medium focus:outline-none focus:ring-2 focus:ring-amber-500"
            >
              <option value="compliant">Compliant Session</option>
              <option value="inflated_attendance">Inflated Attendance Claim</option>
              <option value="missing_machine">Missing Equipment Deficit</option>
              <option value="missing_ppe">Severe PPE Violation</option>
              <option value="instructor_absent">Instructor Absent from Podium</option>
              <option value="capacity_deficit">Workstation Capacity Deficit</option>
              <option value="idle_session">Prolonged Inactivity / Idle</option>
              <option value="poor_quality">Poor Quality / Occlusion</option>
            </select>
          </div>

          {/* Demo Looping Toggle */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">
              Camera Source Mode
            </label>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setIsDemoMode(!isDemoMode)}
                className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium border flex items-center justify-center gap-1.5 transition ${
                  isDemoMode
                    ? 'bg-teal-50 dark:bg-teal-950/60 text-teal-800 dark:text-teal-200 border-teal-300 dark:border-teal-800'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-300 dark:border-slate-700'
                }`}
              >
                {isDemoMode ? <Play className="w-3.5 h-3.5 text-teal-600" /> : <Pause className="w-3.5 h-3.5" />}
                <span>{isDemoMode ? 'Demo Video' : 'Physical RTSP'}</span>
              </button>
            </div>
          </div>

          {/* Centre Streaming Policy Toggle */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">
              Centre Privacy Policy
            </label>
            <button
              onClick={handleToggleStreamingPolicy}
              className={`w-full px-3 py-2 rounded-lg text-xs font-medium border flex items-center justify-center gap-1.5 transition ${
                activeCentre?.live_streaming_enabled !== false
                  ? 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-200 border-emerald-300 dark:border-emerald-800'
                  : 'bg-rose-50 dark:bg-rose-950/60 text-rose-800 dark:text-rose-200 border-rose-300 dark:border-rose-800'
              }`}
              title="Click to toggle streaming permission for this skilling centre"
            >
              {activeCentre?.live_streaming_enabled !== false ? (
                <>
                  <Wifi className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                  <span>Streaming Allowed</span>
                </>
              ) : (
                <>
                  <WifiOff className="w-3.5 h-3.5 text-rose-600 dark:text-rose-400" />
                  <span>Streaming Disabled</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Live Simulation Controls Bar */}
        <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <Sliders className="w-3.5 h-3.5 text-gov-600 dark:text-gov-400" />
            <span className="font-semibold text-slate-700 dark:text-slate-300">
              Demo Quota Simulator:
            </span>
            <span className="text-slate-500 dark:text-slate-400">Claimed Attendance:</span>
            <span className="font-bold text-gov-800 dark:text-gov-200 px-1.5 py-0.5 rounded bg-gov-100 dark:bg-gov-950 border border-gov-200 dark:border-gov-800">
              {claimedAttendance} trainees
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => handleUpdateClaimedQuota(20)}
              className="px-2.5 py-1 rounded bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300 font-semibold border border-rose-200 dark:border-rose-900 hover:bg-rose-200 transition"
              title="Set claimed quota to 20 vs 5 detected (Ratio: 25% < 70% threshold)"
            >
              Simulate Mismatch (20 Claimed ⚠️)
            </button>
            <button
              onClick={() => handleUpdateClaimedQuota(6)}
              className="px-2.5 py-1 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 font-semibold border border-emerald-200 dark:border-emerald-900 hover:bg-emerald-200 transition"
              title="Set claimed quota to 6 vs 5 detected (Ratio: 83% >= 70% threshold)"
            >
              Simulate Compliant (6 Claimed ✅)
            </button>
            <input
              type="range"
              min="0"
              max="30"
              value={claimedAttendance}
              onChange={(e) => handleUpdateClaimedQuota(Number(e.target.value))}
              className="w-24 sm:w-32 accent-gov-600 cursor-pointer"
            />
          </div>
        </div>
      </div>

      {/* Multi-Centre Wall View vs Single Camera View */}
      {viewMode === 'wall' ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between bg-slate-900 text-white px-4 py-3 rounded-xl border border-slate-800 shadow-sm">
            <div className="flex items-center gap-2.5">
              <LayoutGrid className="w-5 h-5 text-teal-400" />
              <div>
                <h2 className="text-sm font-bold">Multi-Centre Monitoring Wall (4 Simultaneous Feeds)</h2>
                <p className="text-[11px] text-slate-400">Low-bandwidth streaming (480px, 5.0 FPS) across vocational trade centres.</p>
              </div>
            </div>
            <button
              onClick={() => {
                setReconnectKey((k) => k + 1);
                refetchWall();
              }}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5 transition"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Refresh Wall</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {(wallData?.wall_centres || []).slice(0, 4).map((wc: any) => {
              const mismatch = wc.current_headcount < 0.70 * wc.claimed_attendance && wc.claimed_attendance > 0;
              return (
                <div
                  key={wc.centre_id}
                  className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-sm flex flex-col transition hover:border-gov-400"
                >
                  {/* Card Header */}
                  <div className="px-4 py-2.5 bg-slate-50 dark:bg-slate-850 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                    <div>
                      <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100">
                        {wc.centre_name}
                      </h3>
                      <p className="text-[10px] text-slate-400 font-mono">
                        {wc.district}, {wc.state} • CAM: {wc.camera_id}
                      </p>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-gov-50 dark:bg-gov-950 text-gov-700 dark:text-gov-300 border border-gov-200 dark:border-gov-800 uppercase">
                      {wc.trade_id.replace('_', ' ')}
                    </span>
                  </div>

                  {/* Video Viewport (Low-bandwidth MJPEG) */}
                  <div className="aspect-video w-full bg-slate-950 relative flex items-center justify-center">
                    <img
                      key={`wall-${wc.camera_id}-${reconnectKey}`}
                      src={`${api.getCameraStreamUrl(wc.camera_id, { maxWidth: 480, fps: 5.0, scenario: wc.current_scenario })}&t=${reconnectKey}`}
                      alt={wc.centre_name}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                    {/* Status scanline overlay */}
                    <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-slate-950/80 backdrop-blur-sm text-[10px] text-emerald-400 font-mono flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                      <span>LIVE 5.0 FPS</span>
                    </div>

                    <div className="absolute top-2 right-2 px-2 py-0.5 rounded bg-slate-950/80 backdrop-blur-sm text-[10px] text-slate-300">
                      ZERO PII
                    </div>
                  </div>

                  {/* Status Badges Row */}
                  <div className="px-4 py-3 bg-white dark:bg-slate-900 grid grid-cols-3 gap-2 border-b border-slate-100 dark:border-slate-800 text-center">
                    {/* Attendance */}
                    <div className="p-1.5 rounded-lg bg-slate-50 dark:bg-slate-800/60">
                      <p className="text-[10px] text-slate-400">Headcount</p>
                      <p className={`text-xs font-bold ${mismatch ? 'text-rose-600 dark:text-rose-400' : 'text-slate-800 dark:text-slate-200'}`}>
                        {wc.current_headcount} / {wc.claimed_attendance}
                      </p>
                    </div>

                    {/* Compliance Score */}
                    <div className="p-1.5 rounded-lg bg-slate-50 dark:bg-slate-800/60">
                      <p className="text-[10px] text-slate-400">Compliance</p>
                      <p className={`text-xs font-bold ${wc.compliance_score >= 80 ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'}`}>
                        {Math.round(wc.compliance_score)}%
                      </p>
                    </div>

                    {/* Active Alerts */}
                    <div className="p-1.5 rounded-lg bg-slate-50 dark:bg-slate-800/60">
                      <p className="text-[10px] text-slate-400">Open Alerts</p>
                      <p className={`text-xs font-bold ${wc.active_alerts_count > 0 ? 'text-rose-600 dark:text-rose-400' : 'text-emerald-600 dark:text-emerald-400'}`}>
                        {wc.active_alerts_count} Active
                      </p>
                    </div>
                  </div>

                  {/* Card Footer: Scenario Injector & Inspect */}
                  <div className="px-4 py-2.5 bg-slate-50 dark:bg-slate-850 flex items-center justify-between gap-2 text-xs">
                    <div className="flex items-center gap-1.5 flex-1 max-w-[240px]">
                      <Sparkles className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                      <select
                        value={wc.current_scenario || 'compliant'}
                        onChange={(e) => handleScenarioChange(e.target.value, wc.camera_id)}
                        className="w-full text-[11px] rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1 text-slate-800 dark:text-slate-200 font-medium"
                        title="Inject demonstration scenario for this centre"
                      >
                        <option value="compliant">Compliant Session</option>
                        <option value="inflated_attendance">Inflated Attendance</option>
                        <option value="missing_machine">Missing Equipment</option>
                        <option value="missing_ppe">Missing PPE Violation</option>
                        <option value="instructor_absent">Instructor Absent</option>
                        <option value="capacity_deficit">Capacity Deficit</option>
                        <option value="idle_session">Idle Trainees</option>
                        <option value="poor_quality">Poor Quality / Occlusion</option>
                      </select>
                    </div>

                    <button
                      onClick={() => {
                        setSelectedCentreId(wc.centre_id);
                        setSelectedCameraId(wc.camera_id);
                        setViewMode('single');
                      }}
                      className="px-2.5 py-1 rounded text-[11px] font-semibold text-gov-600 dark:text-gov-400 hover:bg-gov-50 dark:hover:bg-gov-950 transition flex items-center gap-1"
                    >
                      <span>Inspect Feed</span>
                      <ExternalLink className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        /* Main Monitoring Body: Left Video Feeds, Right Live Reconciliation Panel */
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Video Feeds (2 Cols on lg) */}
          <div className="lg:col-span-2 space-y-4">
          {/* Main Video Viewport Container */}
          <div className="rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 bg-slate-950 shadow-md relative">
            {/* Overlay Status Bar */}
            <div className="absolute top-0 left-0 right-0 z-20 bg-gradient-to-b from-slate-950/90 via-slate-950/60 to-transparent p-3 flex flex-wrap items-center justify-between gap-2 pointer-events-none">
              {/* Left Chips */}
              <div className="flex items-center gap-2 pointer-events-auto">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-bold bg-rose-600 text-white shadow-sm">
                  <span className="w-2 h-2 rounded-full bg-white animate-pulse"></span>
                  LIVE FEED
                </span>

                <span className="px-2 py-1 rounded-md text-[11px] font-semibold bg-slate-900/80 text-slate-200 border border-slate-700/60 backdrop-blur-sm">
                  {activeCamera?.id || 'CAM_01'}
                </span>

                <span className="hidden sm:inline-block px-2 py-1 rounded-md text-[11px] font-medium bg-slate-900/80 text-emerald-400 border border-slate-700/60 backdrop-blur-sm">
                  {telemetry?.fps ? `${telemetry.fps} FPS` : '7.5 FPS'}
                </span>

                <span className="hidden sm:inline-block px-2 py-1 rounded-md text-[11px] font-mono text-slate-300 bg-slate-900/80 border border-slate-700/60">
                  640x360
                </span>

                <span
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-700/60 backdrop-blur-sm"
                  title="Frame Quality: Blur & Brightness nominal, reference correlate > 0.85"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                  Quality: Reliable
                </span>
              </div>

              {/* Right Privacy & Snapshot Badges */}
              <div className="flex items-center gap-2 pointer-events-auto">
                {isSnapshotMode && (
                  <span className="px-2 py-1 rounded-md text-[11px] font-semibold bg-amber-500/90 text-white backdrop-blur-sm">
                    Snapshot Mode (7s)
                  </span>
                )}

                <div
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-semibold bg-teal-500/20 text-teal-300 border border-teal-500/40 backdrop-blur-sm"
                  title="Strict DPDP compliance: Person faces and bodies are heavily blurred directly at edge detector before frame leaves device. No raw footage recorded."
                >
                  <ShieldCheck className="w-3.5 h-3.5 text-teal-400" />
                  <span>Anonymised • Not recorded</span>
                </div>
              </div>
            </div>

            {/* Video Viewport Area */}
            <div className="aspect-video w-full bg-slate-950 flex items-center justify-center relative">
              {isStreamingForbidden ? (
                /* Centre Streaming Disabled Policy State */
                <div className="p-8 text-center space-y-3 max-w-md">
                  <div className="w-12 h-12 rounded-full bg-rose-950/70 text-rose-400 border border-rose-800 flex items-center justify-center mx-auto">
                    <EyeOff className="w-6 h-6" />
                  </div>
                  <h3 className="text-sm font-bold text-slate-100">
                    Live Streaming Disabled for Centre
                  </h3>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    According to the government skilling monitoring policy, live video streaming is currently turned off for{' '}
                    <strong className="text-slate-200">{activeCentre?.name}</strong>. Periodic metadata counts continue syncing via edge agent.
                  </p>
                  <button
                    onClick={handleToggleStreamingPolicy}
                    className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-gov-600 text-white hover:bg-gov-500 transition"
                  >
                    Enable Streaming for this Centre
                  </button>
                </div>
              ) : isCameraOffline && !isDemoMode ? (
                /* Camera Offline State */
                <div className="p-8 text-center space-y-3 max-w-md">
                  <div className="w-12 h-12 rounded-full bg-slate-900 text-slate-400 border border-slate-800 flex items-center justify-center mx-auto">
                    <WifiOff className="w-6 h-6" />
                  </div>
                  <h3 className="text-sm font-bold text-slate-100">
                    Camera Offline ({activeCamera?.id})
                  </h3>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    Edge camera device is not transmitting heartbeats or video frames. Automatic reconnect is active in background.
                  </p>
                  <button
                    onClick={() => setIsDemoMode(true)}
                    className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-teal-600 text-white hover:bg-teal-500 transition"
                  >
                    Switch to Demo Video Feed
                  </button>
                </div>
              ) : streamError ? (
                /* Reconnection / Error State */
                <div className="p-8 text-center space-y-3 max-w-md">
                  <div className="w-12 h-12 rounded-full bg-amber-950/70 text-amber-400 border border-amber-800 flex items-center justify-center mx-auto">
                    <RefreshCw className="w-6 h-6 animate-spin" />
                  </div>
                  <h3 className="text-sm font-bold text-slate-100">
                    Connecting to Edge Stream...
                  </h3>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    Stream interrupted. Reconnecting (attempt {reconnectAttempts}/4)...
                  </p>
                  <button
                    onClick={handleManualReconnect}
                    className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-gov-600 text-white hover:bg-gov-500 transition"
                  >
                    Retry Now
                  </button>
                </div>
              ) : (
                /* Active Video Stream Element */
                <>
                  <img
                    key={`${selectedCameraId}-${reconnectKey}`}
                    src={streamUrl}
                    alt={`Live feed from ${activeCamera?.id}`}
                    className="w-full h-full object-contain"
                    onLoad={() => setStreamLoading(false)}
                    onError={handleStreamError}
                  />

                  {streamLoading && (
                    <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center">
                      <div className="flex items-center gap-2.5 text-xs text-slate-300 font-medium">
                        <RefreshCw className="w-4 h-4 animate-spin text-gov-400" />
                        <span>Initializing edge detection stream...</span>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Bottom Feed Metadata Footer */}
            <div className="px-4 py-2.5 bg-slate-900 border-t border-slate-800 flex flex-wrap items-center justify-between text-[11px] text-slate-400">
              <div className="flex items-center gap-3">
                <span>
                  Active Batch:{' '}
                  <strong className="text-slate-200">
                    {telemetry?.active_batch?.name || 'Solar Technician Level 4'}
                  </strong>
                </span>
                <span>•</span>
                <span>
                  Primary Zone: <strong className="text-teal-400">Classroom</strong>
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span>Viewer Lifecycle:</span>
                <span className="font-semibold text-emerald-400">Active (Auto-stops on exit)</span>
              </div>
            </div>
          </div>

          {/* Grid Layout Expansion (If 2 or 4 cams selected) */}
          {gridLayout !== '1' && (
            <div className="space-y-2">
              <h3 className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                Multi-Camera Wall Grid ({gridLayout} Views)
              </h3>
              <div className={`grid gap-3 ${gridLayout === '2' ? 'grid-cols-2' : 'grid-cols-2 sm:grid-cols-2'}`}>
                {centreCameras.slice(0, Number(gridLayout)).map((cam) => (
                  <div
                    key={cam.id}
                    onClick={() => setSelectedCameraId(cam.id)}
                    className={`rounded-lg overflow-hidden border p-1 bg-slate-900 cursor-pointer transition ${
                      cam.id === selectedCameraId
                        ? 'border-gov-500 ring-2 ring-gov-500/30'
                        : 'border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="aspect-video bg-slate-950 relative overflow-hidden rounded flex items-center justify-center">
                      <img
                        src={api.getCameraSnapshotUrl(cam.id)}
                        alt={cam.id}
                        className="w-full h-full object-cover"
                        loading="lazy"
                      />
                      <div className="absolute bottom-1 left-1 px-1.5 py-0.5 rounded bg-slate-950/80 text-[10px] text-white font-mono">
                        {cam.id}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Live Analysis, Attendance Gauge, Equipment Checklist, Alert Ticker */}
        <div className="space-y-4">
          {/* Card 1: Live Headcount & Claimed Attendance Reconciliation */}
          <div
            className={`rounded-xl border p-5 shadow-sm transition-colors ${
              isMismatch
                ? 'bg-rose-50/70 dark:bg-rose-950/30 border-rose-300 dark:border-rose-900'
                : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800'
            }`}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Users
                  className={`w-4 h-4 ${
                    isMismatch ? 'text-rose-600 dark:text-rose-400' : 'text-gov-600 dark:text-gov-400'
                  }`}
                />
                <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                  Attendance Reconciliation
                </h3>
              </div>
              <span
                className={`px-2 py-0.5 rounded text-[11px] font-bold border ${
                  isMismatch
                    ? 'bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-200 border-rose-300 dark:border-rose-800'
                    : 'bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-200 border-emerald-300 dark:border-emerald-800'
                }`}
              >
                {isMismatch ? 'MISMATCH DETECTED' : 'COMPLIANT'}
              </span>
            </div>

            {/* Big Metrics Split */}
            <div className="grid grid-cols-2 gap-3 py-2 border-y border-slate-200/60 dark:border-slate-800">
              <div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">
                  Detected Trainees
                </p>
                <p className="text-2xl font-extrabold text-slate-900 dark:text-slate-100">
                  {detectedHeadcount}
                </p>
                <p className="text-[10px] text-slate-400">Smoothed headcount</p>
              </div>

              <div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">
                  Claimed Quota
                </p>
                <p className="text-2xl font-extrabold text-slate-900 dark:text-slate-100">
                  {activeClaimed}
                </p>
                <p className="text-[10px] text-slate-400">Sanctioned register</p>
              </div>
            </div>

            {/* Gauge Progress Bar */}
            <div className="mt-4 space-y-1.5">
              <div className="flex justify-between text-xs font-semibold">
                <span className="text-slate-600 dark:text-slate-400">Attendance Ratio:</span>
                <span
                  className={
                    isMismatch
                      ? 'text-rose-600 dark:text-rose-400 font-bold'
                      : 'text-emerald-600 dark:text-emerald-400 font-bold'
                  }
                >
                  {attendancePercent}% (Threshold: 70%)
                </span>
              </div>

              <div className="relative w-full h-3 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-500 rounded-full ${
                    isMismatch ? 'bg-rose-500' : 'bg-emerald-500'
                  }`}
                  style={{ width: `${Math.min(100, attendancePercent)}%` }}
                ></div>
                {/* 70% threshold tick line */}
                <div
                  className="absolute top-0 bottom-0 w-0.5 bg-slate-900 dark:bg-white z-10"
                  style={{ left: '70%' }}
                  title="70% Compliance Threshold"
                ></div>
              </div>

              <p className="text-[11px] text-slate-500 dark:text-slate-400 pt-1">
                {isMismatch
                  ? `Deficit of ${activeClaimed - detectedHeadcount} trainees. Headcount is below mandatory 70% threshold.`
                  : 'Attendance satisfies sanctioned capacity requirements.'}
              </p>
            </div>

            {/* Sub-zone Headcount Breakdown */}
            <div className="mt-3 pt-3 border-t border-slate-200/60 dark:border-slate-800 flex items-center justify-between text-xs">
              <span className="text-slate-500 dark:text-slate-400">Zone Breakdown:</span>
              <div className="flex gap-2">
                <span className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[11px] font-medium text-slate-700 dark:text-slate-300">
                  Classroom: {classroomTelemetry?.smoothed_count ?? 5}
                </span>
                <span className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[11px] font-medium text-slate-700 dark:text-slate-300">
                  Workshop: {telemetry?.zones?.workshop?.smoothed_count ?? 0}
                </span>
              </div>
            </div>
          </div>

          {/* Card: Vocational Trade Compliance Checks (Aggregate, Zero-PII) */}
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm space-y-3.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-gov-600 dark:text-gov-400" />
                <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                  Trade Compliance Checks
                </h3>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-teal-50 dark:bg-teal-950/70 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
                AGGREGATE • NO PII
              </span>
            </div>

            <p className="text-[10px] text-slate-400 italic">
              Automated rules engine signals evaluated per sampling window. Never identifies individuals or stores crops.
            </p>

            <div className="space-y-2.5 text-xs">
              {/* Check 1: Instructor Presence */}
              <div className="p-2.5 rounded-lg border border-slate-100 dark:border-slate-800/80 bg-slate-50/50 dark:bg-slate-800/40 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <UserCheck className="w-3.5 h-3.5 text-slate-500" />
                  <div>
                    <p className="font-semibold text-slate-800 dark:text-slate-200">Instructor Presence</p>
                    <p className="text-[10px] text-slate-400">Anonymous podium occupancy</p>
                  </div>
                </div>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                    telemetry?.compliance_metrics?.instructor_present ?? true
                      ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                      : 'bg-rose-50 dark:bg-rose-950 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800'
                  }`}
                >
                  {telemetry?.compliance_metrics?.instructor_present ?? true ? 'PRESENT' : 'ABSENT'}
                </span>
              </div>

              {/* Check 2: Aggregate PPE Compliance */}
              <div className="p-2.5 rounded-lg border border-slate-100 dark:border-slate-800/80 bg-slate-50/50 dark:bg-slate-800/40 space-y-1.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <HardHat className="w-3.5 h-3.5 text-slate-500" />
                    <div>
                      <p className="font-semibold text-slate-800 dark:text-slate-200">Aggregate PPE Compliance</p>
                      <p className="text-[10px] text-slate-400">
                        {telemetry?.compliance_metrics?.ppe_compliance?.wearing_count ?? detectedHeadcount} of{' '}
                        {telemetry?.compliance_metrics?.ppe_compliance?.total_persons ?? detectedHeadcount} trainees protected
                      </p>
                    </div>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                      (telemetry?.compliance_metrics?.ppe_compliance?.status ?? 'COMPLIANT') === 'COMPLIANT'
                        ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                        : 'bg-rose-50 dark:bg-rose-950 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800'
                    }`}
                  >
                    {Math.round((telemetry?.compliance_metrics?.ppe_compliance?.compliance_rate ?? 0.88) * 100)}% OK
                  </span>
                </div>
                {/* Micro progress bar */}
                <div className="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${
                      (telemetry?.compliance_metrics?.ppe_compliance?.status ?? 'COMPLIANT') === 'COMPLIANT'
                        ? 'bg-emerald-500'
                        : 'bg-rose-500'
                    }`}
                    style={{
                      width: `${Math.round((telemetry?.compliance_metrics?.ppe_compliance?.compliance_rate ?? 0.88) * 100)}%`,
                    }}
                  />
                </div>
              </div>

              {/* Check 3: Safety Items (Extinguisher & First-Aid) */}
              <div className="p-2.5 rounded-lg border border-slate-100 dark:border-slate-800/80 bg-slate-50/50 dark:bg-slate-800/40 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Flame className="w-3.5 h-3.5 text-slate-500" />
                  <div>
                    <p className="font-semibold text-slate-800 dark:text-slate-200">Safety Equipment</p>
                    <p className="text-[10px] text-slate-400">Fire extinguisher & first-aid kit</p>
                  </div>
                </div>
                <div className="flex gap-1.5">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                      telemetry?.compliance_metrics?.safety_items?.fire_extinguisher ?? true
                        ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                        : 'bg-rose-50 dark:bg-rose-950 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800'
                    }`}
                  >
                    EXT: {telemetry?.compliance_metrics?.safety_items?.fire_extinguisher ?? true ? 'YES' : 'NO'}
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                    KIT: YES
                  </span>
                </div>
              </div>

              {/* Check 4 & 5: Capacity & Activity */}
              <div className="grid grid-cols-2 gap-2">
                <div className="p-2 rounded-lg border border-slate-100 dark:border-slate-800/80 bg-slate-50/50 dark:bg-slate-800/40">
                  <p className="text-[10px] text-slate-400">Workstation Capacity</p>
                  <p className="text-xs font-bold text-slate-800 dark:text-slate-200 mt-0.5">
                    {telemetry?.compliance_metrics?.workstation_capacity?.status === 'DEFICIT' ? (
                      <span className="text-rose-600 dark:text-rose-400 font-bold">DEFICIT</span>
                    ) : (
                      <span className="text-emerald-600 dark:text-emerald-400">SATISFIED</span>
                    )}
                  </p>
                </div>
                <div className="p-2 rounded-lg border border-slate-100 dark:border-slate-800/80 bg-slate-50/50 dark:bg-slate-800/40">
                  <p className="text-[10px] text-slate-400">Zone Activity State</p>
                  <p className="text-xs font-bold mt-0.5 text-teal-600 dark:text-teal-400 uppercase">
                    {telemetry?.compliance_metrics?.activity_state ?? 'ACTIVE'}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Card 2: Sanctioned Equipment Checklist */}
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Wrench className="w-4 h-4 text-gov-600 dark:text-gov-400" />
                <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                  Sanctioned Equipment
                </h3>
              </div>
              <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
                Classroom & Workshop
              </span>
            </div>

            <p className="text-[10px] text-slate-400 italic">
              Operability is a heuristic indication based on vision signals (screen activity, power LEDs, proximity), not an engineering diagnostic.
            </p>

            <div className="divide-y divide-slate-100 dark:divide-slate-800 text-xs">
              {telemetry?.equipment && telemetry.equipment.length > 0 ? (
                telemetry.equipment.map((item, idx) => (
                  <div key={idx} className="py-2 flex items-center justify-between">
                    <div>
                      <p className="font-semibold text-slate-800 dark:text-slate-200 capitalize">
                        {item.item}
                      </p>
                      <p className="text-[10px] text-slate-400">Zone: {item.zone}</p>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-slate-600 dark:text-slate-400 font-mono">
                        {item.detected} / {item.expected}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                          item.status === 'MATCH'
                            ? 'bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                            : 'bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800'
                        }`}
                      >
                        {item.status}
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                /* Standard mock items if telemetry pending */
                <>
                  <div className="py-2 flex items-center justify-between">
                    <div>
                      <p className="font-semibold text-slate-800 dark:text-slate-200">Chairs</p>
                      <p className="text-[10px] text-slate-400">Classroom</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-slate-600 dark:text-slate-400 font-mono">4 / 6</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                        DEFICIT
                      </span>
                    </div>
                  </div>

                  <div className="py-2 flex items-center justify-between">
                    <div>
                      <p className="font-semibold text-slate-800 dark:text-slate-200">Computers</p>
                      <p className="text-[10px] text-slate-400">Classroom</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-slate-600 dark:text-slate-400 font-mono">4 / 4</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                        MATCH
                      </span>
                    </div>
                  </div>

                  <div className="py-2 flex items-center justify-between">
                    <div>
                      <p className="font-semibold text-slate-800 dark:text-slate-200">Workbenches</p>
                      <p className="text-[10px] text-slate-400">Workshop</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-slate-600 dark:text-slate-400 font-mono">2 / 2</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                        MATCH
                      </span>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Card 3: Real-Time Live Alert Ticker */}
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 dark:text-rose-400" />
                <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                  Live Alert Ticker
                </h3>
              </div>
              <Link
                to="/alerts"
                className="text-xs font-semibold text-gov-600 dark:text-gov-400 hover:underline"
              >
                View Full Queue →
              </Link>
            </div>

            <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
              {liveAlerts.length > 0 ? (
                liveAlerts.map((alert, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 rounded-lg border border-rose-200 dark:border-rose-900/60 bg-rose-50/60 dark:bg-rose-950/20 text-xs space-y-1 transition hover:bg-rose-100/60"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-rose-800 dark:text-rose-300 text-[11px] uppercase tracking-wide">
                        {alert.type}
                      </span>
                      <span className="text-[10px] text-slate-400 font-mono">
                        {alert.timestamp}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-700 dark:text-slate-300 leading-snug">
                      {alert.message}
                    </p>
                  </div>
                ))
              ) : isMismatch ? (
                <div className="p-2.5 rounded-lg border border-rose-200 dark:border-rose-900/60 bg-rose-50/60 dark:bg-rose-950/20 text-xs space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-rose-800 dark:text-rose-300 text-[11px]">
                      ATTENDANCE_MISMATCH
                    </span>
                    <span className="text-[10px] text-slate-400">Just now</span>
                  </div>
                  <p className="text-[11px] text-slate-700 dark:text-slate-300">
                    Classroom headcount ({detectedHeadcount}) is below 70% threshold of claimed attendance ({activeClaimed}).
                  </p>
                </div>
              ) : (
                <div className="py-6 text-center text-xs text-slate-400 space-y-1">
                  <CheckCircle2 className="w-5 h-5 text-emerald-500 mx-auto" />
                  <p className="font-semibold text-slate-600 dark:text-slate-400">
                    No active compliance alerts
                  </p>
                  <p className="text-[10px]">Edge detector reports normal operations</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    )}
  </div>
);
};

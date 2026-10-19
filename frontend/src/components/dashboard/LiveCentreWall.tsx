import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Radio,
  VideoOff,
  ShieldCheck,
  AlertTriangle,
  ArrowRight,
  Maximize2,
  Users,
  Building2,
  RefreshCw,
  Sliders,
} from 'lucide-react';
import { api } from '../../api/client';
import { WallCentreItem } from '../../types';
import { ScoreRing } from '../common/ScoreRing';
import { LoadingSkeleton } from '../common/LoadingSkeleton';

export const LiveCentreWall: React.FC = () => {
  const navigate = useNavigate();
  const [snapshotTimestamp, setSnapshotTimestamp] = useState<number>(Date.now());

  // Fetch wall metadata with auto-refresh every 5s
  const { data: wallData, isLoading, isError, refetch } = useQuery({
    queryKey: ['streaming-wall'],
    queryFn: () => api.getMultiCentreWall(),
    refetchInterval: 5000,
  });

  // Snapshot cache buster interval every 5s
  useEffect(() => {
    const timer = setInterval(() => {
      setSnapshotTimestamp(Date.now());
    }, 5000);
    return () => clearInterval(timer);
  }, []);

  const centres: WallCentreItem[] = wallData?.wall_centres || [];

  const getStatusChipStyle = (chip?: string) => {
    switch (chip) {
      case 'OK':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800';
      case 'Mismatch':
        return 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-800';
      case 'Equipment':
        return 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800';
      case 'Offline':
      default:
        return 'bg-slate-100 text-slate-700 border-slate-300 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700';
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <LoadingSkeleton rows={1} className="h-6 w-48" />
          <LoadingSkeleton rows={1} className="h-6 w-32" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-64 rounded-xl bg-slate-100 dark:bg-slate-800/60 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (isError || centres.length === 0) {
    return null;
  }

  return (
    <section className="space-y-4" aria-label="Live Centre Wall">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm sm:text-base font-extrabold text-slate-900 dark:text-slate-100 flex items-center gap-2 tracking-tight">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
              </span>
              Live Centre Wall
            </h2>
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
              {centres.length} Monitored Centres
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Real-time low-resolution edge feeds with automatic person blurring and trade analytics.
          </p>
        </div>

        {/* Privacy Safe & Navigation Links */}
        <div className="flex items-center gap-2">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
            <span>Anonymised • Not recorded</span>
          </div>

          <Link
            to="/live"
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold bg-gov-600 hover:bg-gov-700 text-white shadow-xs transition"
          >
            <span>Open Wall View</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>

      {/* Grid of 6 Centre Tiles */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4.5">
        {centres.map((centre) => {
          const isOffline = centre.camera_status === 'offline';
          const matchRatio = centre.claimed_attendance > 0 ? centre.current_headcount / centre.claimed_attendance : 1;
          const isMismatch = matchRatio < 0.70;
          const progressPercent = Math.min(100, Math.max(0, Math.round(matchRatio * 100)));

          return (
            <div
              key={centre.centre_id}
              onClick={() => navigate(`/live?centre=${centre.centre_id}&camera=${centre.camera_id}`)}
              className="group rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs hover:shadow-md transition-all cursor-pointer overflow-hidden flex flex-col justify-between"
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  navigate(`/live?centre=${centre.centre_id}&camera=${centre.camera_id}`);
                }
              }}
              aria-label={`Open Live Monitor for ${centre.centre_name}`}
            >
              {/* Card Header */}
              <div className="p-3.5 border-b border-slate-100 dark:border-slate-800/80 flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-bold text-slate-900 dark:text-slate-100 group-hover:text-gov-600 dark:group-hover:text-gov-400 transition-colors truncate block">
                      {centre.centre_name}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 text-[11px] text-slate-500 dark:text-slate-400 mt-0.5 truncate">
                    <span className="font-semibold text-slate-700 dark:text-slate-300">
                      {centre.trade_name || centre.trade_id.replace(/_/g, ' ').toUpperCase()}
                    </span>
                    <span>•</span>
                    <span className="truncate">{centre.district}, {centre.state}</span>
                  </div>
                </div>

                {/* Status Chip */}
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded-full border uppercase tracking-wider flex-shrink-0 ${getStatusChipStyle(
                    centre.status_chip
                  )}`}
                >
                  {centre.status_chip || (isOffline ? 'Offline' : 'OK')}
                </span>
              </div>

              {/* Feed Thumbnail / Placeholder */}
              <div className="relative aspect-video bg-slate-950 flex items-center justify-center overflow-hidden">
                {centre.has_footage && !isOffline ? (
                  <img
                    src={`${centre.snapshot_url}?t=${snapshotTimestamp}`}
                    alt={`Live feed from ${centre.centre_name}`}
                    className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-102"
                    loading="lazy"
                    onError={(e) => {
                      // Fallback gracefully on image error
                      (e.target as HTMLElement).style.display = 'none';
                    }}
                  />
                ) : (
                  /* Missing footage or offline placeholder */
                  <div className="flex flex-col items-center justify-center p-4 text-center">
                    <VideoOff className="w-8 h-8 text-slate-500 mb-1.5" />
                    <span className="text-xs font-semibold text-slate-300">
                      {centre.has_footage ? 'Camera Offline' : 'Simulated feed (no footage provided)'}
                    </span>
                    <span className="text-[10px] text-slate-500 mt-0.5">
                      {centre.has_footage ? 'Edge device heartbeat pending' : 'CCTV edge stream standby'}
                    </span>
                  </div>
                )}

                {/* Anonymised Overlay Badge */}
                <div className="absolute top-2 left-2 z-10 flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-900/80 backdrop-blur-xs text-[10px] font-medium text-slate-200 border border-slate-700/60">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  <span>5 FPS • Anonymised</span>
                </div>

                <div className="absolute bottom-2 right-2 z-10 opacity-0 group-hover:opacity-100 transition-opacity bg-slate-900/90 text-white p-1 rounded-md">
                  <Maximize2 className="w-3.5 h-3.5" />
                </div>
              </div>

              {/* Card Footer: Headcount vs Claimed + Compliance Score */}
              <div className="p-3 bg-slate-50/50 dark:bg-slate-900/50 border-t border-slate-100 dark:border-slate-800 space-y-2">
                {/* Attendance Discrepancy Bar */}
                <div>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-slate-500 dark:text-slate-400 flex items-center gap-1 font-medium">
                      <Users className="w-3.5 h-3.5" />
                      Detected / Claimed
                    </span>
                    <span className="font-mono font-bold text-slate-900 dark:text-slate-100">
                      <span className={isMismatch ? 'text-rose-600 dark:text-rose-400 font-extrabold' : 'text-slate-900 dark:text-slate-100'}>
                        {centre.current_headcount}
                      </span>
                      <span className="text-slate-400 mx-0.5">/</span>
                      <span>{centre.claimed_attendance}</span>
                    </span>
                  </div>

                  <div className="w-full bg-slate-200 dark:bg-slate-800 rounded-full h-1.5 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        isMismatch ? 'bg-rose-500' : 'bg-emerald-500'
                      }`}
                      style={{ width: `${Math.min(100, progressPercent)}%` }}
                    />
                  </div>
                </div>

                {/* Bottom Row: Compliance score and active alerts count */}
                <div className="flex items-center justify-between pt-1 text-xs">
                  <div className="flex items-center gap-1.5">
                    <ScoreRing score={centre.compliance_score} size="sm" showLabel={false} />
                    <span className="font-extrabold text-slate-800 dark:text-slate-200">
                      {centre.compliance_score.toFixed(1)}%
                    </span>
                    <span className="text-[10px] text-slate-400">Score</span>
                  </div>

                  <div className="flex items-center gap-1 text-[11px] text-slate-500 dark:text-slate-400">
                    {centre.active_alerts_count > 0 ? (
                      <span className="inline-flex items-center gap-1 text-rose-600 dark:text-rose-400 font-bold">
                        <AlertTriangle className="w-3 h-3" />
                        {centre.active_alerts_count} alert{centre.active_alerts_count > 1 ? 's' : ''}
                      </span>
                    ) : (
                      <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
                        0 alerts
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
};

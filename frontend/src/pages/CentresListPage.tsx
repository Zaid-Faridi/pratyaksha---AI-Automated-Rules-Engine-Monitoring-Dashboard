import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Building2, ArrowRight, Video, VideoOff } from 'lucide-react';
import { api } from '../api/client';
import { DataTable, Column } from '../components/common/DataTable';
import { ScoreRing } from '../components/common/ScoreRing';
import { StatusBadge } from '../components/common/StatusBadge';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { ErrorState } from '../components/common/ErrorState';
import { Centre, Camera, ComplianceBreakdown } from '../types';

interface CentreTableRow extends Centre {
  compliance?: ComplianceBreakdown;
  cameras?: Camera[];
}

export const CentresListPage: React.FC = () => {
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'COMPLIANT' | 'NEEDS_ATTENTION' | 'NON_COMPLIANT'>('ALL');

  // Fetch centres
  const { data: centres, isLoading: loadingCentres, isError } = useQuery({
    queryKey: ['centres'],
    queryFn: () => api.getCentres(),
  });

  // Fetch cameras
  const { data: cameras } = useQuery({
    queryKey: ['cameras'],
    queryFn: () => api.getCameras(),
  });

  // Fetch summary to obtain compliance map
  const { data: summary } = useQuery({
    queryKey: ['dashboardSummary'],
    queryFn: () => api.getDashboardSummary(),
  });

  // Combine data into table rows
  const tableData: CentreTableRow[] = useMemo(() => {
    if (!centres) return [];

    const compMap: Record<string, ComplianceBreakdown> = {};
    if (summary?.top_non_compliant_centres) {
      summary.top_non_compliant_centres.forEach((item) => {
        compMap[item.centre_id] = item;
      });
    }

    const camMap: Record<string, Camera[]> = {};
    if (cameras) {
      cameras.forEach((cam) => {
        if (!camMap[cam.centre_id]) camMap[cam.centre_id] = [];
        camMap[cam.centre_id].push(cam);
      });
    }

    return centres.map((c) => ({
      ...c,
      compliance: compMap[c.id],
      cameras: camMap[c.id] || [],
    }));
  }, [centres, cameras, summary]);

  // Apply status filter
  const filteredData = useMemo(() => {
    if (statusFilter === 'ALL') return tableData;
    return tableData.filter((row) => {
      const status = row.compliance?.summary_status || 'COMPLIANT';
      return status === statusFilter;
    });
  }, [tableData, statusFilter]);

  const columns: Column<CentreTableRow>[] = [
    {
      header: 'Centre Name & ID',
      accessor: 'name',
      sortable: true,
      render: (row) => (
        <div>
          <Link
            to={`/centres/${row.id}`}
            className="font-bold text-slate-900 dark:text-slate-100 hover:text-gov-600 dark:hover:text-gov-400 block"
          >
            {row.name}
          </Link>
          <span className="text-[11px] text-slate-400 font-mono">ID: {row.id}</span>
        </div>
      ),
    },
    {
      header: 'Location',
      sortable: true,
      render: (row) => (
        <div>
          <span className="font-medium text-slate-800 dark:text-slate-200">{row.district}</span>
          <span className="text-slate-400 block text-[11px]">{row.state}</span>
        </div>
      ),
    },
    {
      header: 'Scheme',
      accessor: 'scheme',
      sortable: true,
      render: (row) => (
        <span className="inline-flex px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
          {row.scheme}
        </span>
      ),
    },
    {
      header: 'Compliance Score',
      sortable: true,
      className: 'text-center',
      render: (row) => {
        const score = row.compliance?.compliance_score ?? 90.0;
        return (
          <div className="inline-flex items-center gap-2">
            <ScoreRing score={score} size="sm" />
            <span className="font-bold text-xs text-slate-800 dark:text-slate-200">{score.toFixed(1)}%</span>
          </div>
        );
      },
    },
    {
      header: 'Camera Health & Heartbeat',
      render: (row) => {
        const cams = row.cameras || [];
        if (cams.length === 0) return <span className="text-slate-400">—</span>;

        const onlineCams = cams.filter((c) => c.status === 'online');
        const latestSeen = cams.find((c) => c.last_seen_at)?.last_seen_at;

        return (
          <div>
            <div className="flex items-center gap-1.5">
              {onlineCams.length === cams.length ? (
                <span className="inline-flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold">
                  <Video className="w-3.5 h-3.5" />
                  {onlineCams.length}/{cams.length} Online
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-[11px] text-rose-600 dark:text-rose-400 font-semibold">
                  <VideoOff className="w-3.5 h-3.5" />
                  {cams.length - onlineCams.length} Offline
                </span>
              )}
            </div>
            {latestSeen && (
              <span className="text-[10px] text-slate-400 block mt-0.5">
                Ping: {new Date(latestSeen).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
          </div>
        );
      },
    },
    {
      header: 'Open Alerts',
      className: 'text-center',
      render: (row) => {
        const count = row.compliance?.open_alerts_count || 0;
        if (count > 0) {
          return (
            <span className="inline-flex px-2 py-0.5 text-xs font-bold rounded-full bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300">
              {count} Open
            </span>
          );
        }
        return <span className="text-emerald-600 dark:text-emerald-400 text-xs font-medium">0 Open</span>;
      },
    },
    {
      header: 'Status',
      className: 'text-center',
      render: (row) => (
        <StatusBadge status={row.compliance?.summary_status || 'COMPLIANT'} />
      ),
    },
    {
      header: 'Action',
      className: 'text-right',
      render: (row) => (
        <Link
          to={`/centres/${row.id}`}
          className="inline-flex items-center gap-1 text-xs font-semibold text-gov-600 hover:text-gov-800 dark:text-gov-400 transition"
        >
          Audit <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      ),
    },
  ];

  if (loadingCentres) {
    return <LoadingSkeleton rows={6} className="h-16" />;
  }

  if (isError || !centres) {
    return <ErrorState message="Could not retrieve the registry of skilling centres." />;
  }

  return (
    <div className="space-y-6 pb-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight flex items-center gap-2">
            <Building2 className="w-6 h-6 text-gov-600" />
            Monitored Skilling Centres
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
            Registered government vocational training institutes, camera statuses, and real-time compliance scores.
          </p>
        </div>

        {/* Filter Tabs */}
        <div className="inline-flex p-1 bg-slate-100 dark:bg-slate-800 rounded-lg text-xs font-semibold text-slate-600 dark:text-slate-300 self-start sm:self-auto">
          {(['ALL', 'COMPLIANT', 'NEEDS_ATTENTION', 'NON_COMPLIANT'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setStatusFilter(tab)}
              className={`px-3 py-1.5 rounded-md transition ${
                statusFilter === tab
                  ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-sm'
                  : 'hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              {tab.replace(/_/g, ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Main Table */}
      <DataTable
        columns={columns}
        data={filteredData}
        searchKey={(row) => `${row.name} ${row.district} ${row.state} ${row.scheme}`}
        searchPlaceholder="Search by centre name, district, state, or scheme..."
        pageSize={8}
      />
    </div>
  );
};

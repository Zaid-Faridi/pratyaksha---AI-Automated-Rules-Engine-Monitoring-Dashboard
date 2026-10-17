import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { MapPin, Filter, Building2, Search, ArrowRight, ShieldAlert } from 'lucide-react';
import { api } from '../api/client';
import { CentresMap } from '../components/map/CentresMap';
import { ScoreRing } from '../components/common/ScoreRing';
import { StatusBadge } from '../components/common/StatusBadge';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { ErrorState } from '../components/common/ErrorState';
import { ComplianceBreakdown } from '../types';

export const MapPage: React.FC = () => {
  const [selectedState, setSelectedState] = useState<string>('all');
  const [selectedDistrict, setSelectedDistrict] = useState<string>('all');
  const [selectedScheme, setSelectedScheme] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [selectedCentreId, setSelectedCentreId] = useState<string | null>(null);

  // Fetch centres list
  const { data: centres, isLoading: loadingCentres, isError: errorCentres } = useQuery({
    queryKey: ['centres'],
    queryFn: () => api.getCentres(),
  });

  // Fetch dashboard summary for compliance mapping
  const { data: summary, isLoading: loadingSummary } = useQuery({
    queryKey: ['dashboardSummary'],
    queryFn: () => api.getDashboardSummary(),
  });

  // Build map of centre_id -> ComplianceBreakdown
  const complianceMap = useMemo(() => {
    const map: Record<string, ComplianceBreakdown> = {};
    if (summary?.top_non_compliant_centres) {
      summary.top_non_compliant_centres.forEach((item) => {
        map[item.centre_id] = item;
      });
    }
    return map;
  }, [summary]);

  // Derived filter options
  const states = useMemo(() => {
    if (!centres) return [];
    return Array.from(new Set(centres.map((c) => c.state))).sort();
  }, [centres]);

  const districts = useMemo(() => {
    if (!centres) return [];
    let list = centres;
    if (selectedState !== 'all') {
      list = list.filter((c) => c.state === selectedState);
    }
    return Array.from(new Set(list.map((c) => c.district))).sort();
  }, [centres, selectedState]);

  const schemes = useMemo(() => {
    if (!centres) return [];
    return Array.from(new Set(centres.map((c) => c.scheme))).sort();
  }, [centres]);

  // Filtered centres list
  const filteredCentres = useMemo(() => {
    if (!centres) return [];
    return centres.filter((c) => {
      if (selectedState !== 'all' && c.state !== selectedState) return false;
      if (selectedDistrict !== 'all' && c.district !== selectedDistrict) return false;
      if (selectedScheme !== 'all' && c.scheme !== selectedScheme) return false;

      if (selectedStatus !== 'all') {
        const comp = complianceMap[c.id];
        const status = comp?.summary_status || 'COMPLIANT';
        if (status !== selectedStatus) return false;
      }
      return true;
    });
  }, [centres, selectedState, selectedDistrict, selectedScheme, selectedStatus, complianceMap]);

  if (loadingCentres || loadingSummary) {
    return (
      <div className="space-y-4">
        <LoadingSkeleton rows={1} className="h-14" />
        <LoadingSkeleton rows={1} className="h-[600px]" />
      </div>
    );
  }

  if (errorCentres || !centres) {
    return <ErrorState message="Could not retrieve geographic centre coordinates." />;
  }

  return (
    <div className="space-y-5 pb-8">
      {/* Page Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight flex items-center gap-2">
          <MapPin className="w-6 h-6 text-gov-600" />
          National Skilling Centres Map View
        </h1>
        <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
          Geographic spatial visualization of monitored centres with real-time compliance pins (Green &ge; 85%, Amber 65–84%, Red &lt; 65%).
        </p>
      </div>

      {/* Filter Bar */}
      <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 dark:text-slate-400">
          <Filter className="w-4 h-4 text-gov-600" />
          <span>Filters:</span>
        </div>

        {/* State Filter */}
        <select
          value={selectedState}
          onChange={(e) => {
            setSelectedState(e.target.value);
            setSelectedDistrict('all');
          }}
          className="text-xs py-1.5 px-3 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-800 dark:text-slate-200 focus:ring-2 focus:ring-gov-500 outline-none"
        >
          <option value="all">All States ({states.length})</option>
          {states.map((st) => (
            <option key={st} value={st}>{st}</option>
          ))}
        </select>

        {/* District Filter */}
        <select
          value={selectedDistrict}
          onChange={(e) => setSelectedDistrict(e.target.value)}
          className="text-xs py-1.5 px-3 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-800 dark:text-slate-200 focus:ring-2 focus:ring-gov-500 outline-none"
        >
          <option value="all">All Districts ({districts.length})</option>
          {districts.map((dst) => (
            <option key={dst} value={dst}>{dst}</option>
          ))}
        </select>

        {/* Scheme Filter */}
        <select
          value={selectedScheme}
          onChange={(e) => setSelectedScheme(e.target.value)}
          className="text-xs py-1.5 px-3 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-800 dark:text-slate-200 focus:ring-2 focus:ring-gov-500 outline-none"
        >
          <option value="all">All Schemes ({schemes.length})</option>
          {schemes.map((sch) => (
            <option key={sch} value={sch}>{sch}</option>
          ))}
        </select>

        {/* Status Filter */}
        <select
          value={selectedStatus}
          onChange={(e) => setSelectedStatus(e.target.value)}
          className="text-xs py-1.5 px-3 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-800 dark:text-slate-200 focus:ring-2 focus:ring-gov-500 outline-none"
        >
          <option value="all">All Compliance Statuses</option>
          <option value="COMPLIANT">Compliant (&ge; 85%)</option>
          <option value="NEEDS_ATTENTION">Needs Attention (65–84%)</option>
          <option value="NON_COMPLIANT">Non-Compliant (&lt; 65%)</option>
        </select>

        <span className="ml-auto text-xs font-medium text-slate-500 dark:text-slate-400">
          Showing <span className="font-bold text-slate-800 dark:text-slate-200">{filteredCentres.length}</span> of {centres.length} centres
        </span>
      </div>

      {/* Map & Centre Sidebar Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
        {/* Map Container */}
        <div className="lg:col-span-3">
          <CentresMap
            centres={filteredCentres}
            complianceMap={complianceMap}
            selectedCentreId={selectedCentreId}
            onSelectCentre={(id) => setSelectedCentreId(id)}
            className="h-[600px] w-full"
          />
        </div>

        {/* Sidebar list of matching centres */}
        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm p-4 flex flex-col h-[600px]">
          <div className="border-b border-slate-200 dark:border-slate-800 pb-3 mb-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
              Matching Centres ({filteredCentres.length})
            </h3>
            <p className="text-[11px] text-slate-400 mt-0.5">Click any centre to focus map</p>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2.5 pr-1 text-xs">
            {filteredCentres.map((c) => {
              const comp = complianceMap[c.id];
              const score = comp ? comp.compliance_score : 90;
              const isSelected = selectedCentreId === c.id;

              return (
                <div
                  key={c.id}
                  onClick={() => setSelectedCentreId(c.id)}
                  className={`p-3 rounded-lg border transition-all cursor-pointer ${
                    isSelected
                      ? 'border-gov-500 bg-gov-50/70 dark:bg-gov-950/40 shadow-sm ring-1 ring-gov-500'
                      : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-slate-50/50 dark:bg-slate-900'
                  }`}
                >
                  <div className="flex items-start justify-between gap-1 mb-1.5">
                    <span className="font-bold text-slate-900 dark:text-slate-100 text-xs line-clamp-1">
                      {c.name}
                    </span>
                    <ScoreRing score={score} size="sm" />
                  </div>

                  <p className="text-[11px] text-slate-500 dark:text-slate-400 mb-2">
                    {c.district}, {c.state} • {c.scheme}
                  </p>

                  <div className="flex items-center justify-between pt-1 border-t border-slate-200/60 dark:border-slate-800/60 text-[11px]">
                    <span className={comp?.open_alerts_count ? 'text-rose-600 font-bold' : 'text-slate-400'}>
                      {comp?.open_alerts_count || 0} Open Alerts
                    </span>
                    <Link
                      to={`/centres/${c.id}`}
                      className="text-gov-600 dark:text-gov-400 hover:underline inline-flex items-center gap-0.5 font-semibold"
                      onClick={(e) => e.stopPropagation()}
                    >
                      Audit <ArrowRight className="w-3 h-3" />
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

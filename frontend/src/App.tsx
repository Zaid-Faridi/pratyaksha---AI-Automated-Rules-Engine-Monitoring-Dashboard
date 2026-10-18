import React, { useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { OverviewPage } from './pages/OverviewPage';
import { LiveMonitorPage } from './pages/LiveMonitorPage';
import { MapPage } from './pages/MapPage';
import { CentresListPage } from './pages/CentresListPage';
import { CentreDetailPage } from './pages/CentreDetailPage';
import { AlertQueuePage } from './pages/AlertQueuePage';
import { CentrePortalPage } from './pages/CentrePortalPage';
import { AuditLogPage } from './pages/AuditLogPage';
import { PrivacyPage } from './pages/PrivacyPage';
import { ThemeProvider } from './context/ThemeContext';
import { api } from './api/client';
import { useQuery } from '@tanstack/react-query';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function DashboardLayout() {
  const qc = useQueryClient();
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Global query for dashboard summary to power alert badges
  const { data: summary } = useQuery({
    queryKey: ['dashboardSummary'],
    queryFn: () => api.getDashboardSummary(),
    refetchInterval: 30000,
  });

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    await qc.invalidateQueries();
    setLastUpdated(new Date());
    setTimeout(() => setIsRefreshing(false), 600);
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
      {/* Top Header */}
      <Header
        lastUpdated={lastUpdated}
        onRefresh={handleManualRefresh}
        isRefreshing={isRefreshing}
        openAlertsCount={summary?.open_alerts_count || 0}
      />

      {/* Main Content Area with Sidebar */}
      <div className="flex-1 max-w-7xl w-full mx-auto flex flex-col md:flex-row">
        <Sidebar openAlertsCount={summary?.open_alerts_count || 0} />

        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-y-auto">
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/live" element={<LiveMonitorPage />} />
            <Route path="/map" element={<MapPage />} />
            <Route path="/centres" element={<CentresListPage />} />
            <Route path="/centres/:id" element={<CentreDetailPage />} />
            <Route path="/alerts" element={<AlertQueuePage />} />
            <Route path="/portal" element={<CentrePortalPage />} />
            <Route path="/audit" element={<AuditLogPage />} />
            <Route path="/privacy" element={<PrivacyPage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <DashboardLayout />
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  );
}

export default App;

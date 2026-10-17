import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ShieldCheck, Moon, Sun, RefreshCw, Bell, Radio } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';

interface HeaderProps {
  lastUpdated?: Date;
  onRefresh?: () => void;
  isRefreshing?: boolean;
  openAlertsCount?: number;
}

export const Header: React.FC<HeaderProps> = ({
  lastUpdated = new Date(),
  onRefresh,
  isRefreshing = false,
  openAlertsCount = 0,
}) => {
  const { theme, toggleTheme } = useTheme();
  const location = useLocation();

  return (
    <header className="sticky top-0 z-30 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Left: Branding & Emblems */}
        <div className="flex items-center gap-3">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-gov-700 to-teal-500 flex items-center justify-center text-white font-bold text-lg shadow-sm">
              प्र
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-lg tracking-tight text-gov-900 dark:text-white">
                  Pratyaksha
                </span>
                <span className="text-xs font-semibold px-1.5 py-0.5 rounded bg-gov-100 dark:bg-gov-950 text-gov-700 dark:text-gov-300 border border-gov-200 dark:border-gov-800">
                  MSDE 26245
                </span>
              </div>
              <p className="text-[10px] text-slate-500 dark:text-slate-400 font-medium">
                AI Skilling Centre Monitoring Unit
              </p>
            </div>
          </Link>

          {/* Privacy Preserving Badge (User requirement: linking to /privacy) */}
          <Link
            to="/privacy"
            className="hidden sm:inline-flex items-center gap-1.5 ml-3 px-2.5 py-1 rounded-full text-xs font-medium bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800 hover:bg-teal-100 dark:hover:bg-teal-900/80 transition"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-teal-600 dark:text-teal-400" />
            <span>Privacy-Preserving</span>
          </Link>
        </div>

        {/* Right: Status, Refresh, Alerts, Dark Mode */}
        <div className="flex items-center gap-2.5 sm:gap-4">
          {/* Live stream status indicator */}
          <div className="hidden md:flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span>Live Sync</span>
            <span className="text-[11px] text-slate-400 dark:text-slate-500">
              ({lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })})
            </span>
          </div>

          {/* Refresh button */}
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={isRefreshing}
              className="p-2 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition disabled:opacity-50"
              title="Refresh Data (Auto-refreshes every 30s)"
              aria-label="Refresh dashboard data"
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-gov-600' : ''}`} />
            </button>
          )}

          {/* Alert Queue Quick Icon */}
          <Link
            to="/alerts"
            className="relative p-2 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition"
            title="Open Compliance Alerts"
            aria-label="View alert queue"
          >
            <Bell className="w-4 h-4" />
            {openAlertsCount > 0 && (
              <span className="absolute top-1 right-1 flex items-center justify-center min-w-[16px] h-4 px-1 text-[10px] font-bold text-white bg-rose-600 rounded-full">
                {openAlertsCount}
              </span>
            )}
          </Link>

          {/* Dark / Light Toggle */}
          <button
            onClick={toggleTheme}
            className="p-2 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition"
            title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            aria-label="Toggle dark mode"
          >
            {theme === 'dark' ? (
              <Sun className="w-4 h-4 text-amber-400" />
            ) : (
              <Moon className="w-4 h-4 text-slate-600" />
            )}
          </button>
        </div>
      </div>
    </header>
  );
};

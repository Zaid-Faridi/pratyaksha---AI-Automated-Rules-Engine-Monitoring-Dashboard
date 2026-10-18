import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  MapPin,
  Building2,
  AlertTriangle,
  ShieldCheck,
} from 'lucide-react';

interface SidebarProps {
  openAlertsCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({ openAlertsCount = 0 }) => {
  const navItems = [
    { to: '/', label: 'Overview', icon: LayoutDashboard },
    { to: '/map', label: 'Map View', icon: MapPin },
    { to: '/centres', label: 'Centres List', icon: Building2 },
    { to: '/alerts', label: 'Alert Queue', icon: AlertTriangle, badge: openAlertsCount },
    { to: '/privacy', label: 'Privacy Policy', icon: ShieldCheck },
  ];

  return (
    <nav className="w-full md:w-64 md:flex-shrink-0 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex md:flex-col transition-colors">
      <div className="w-full p-3 sm:p-4 space-y-1 flex md:flex-col gap-1 overflow-x-auto md:overflow-visible">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${
                  isActive
                    ? 'bg-gov-500 text-white shadow-sm font-semibold'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100'
                }`
              }
            >
              <Icon className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
              <span className="flex-1">{item.label}</span>
              {Boolean(item.badge && item.badge > 0) && (
                <span className="ml-auto px-2 py-0.5 text-[11px] font-bold rounded-full bg-rose-600 text-white">
                  {item.badge}
                </span>
              )}
            </NavLink>
          );
        })}
      </div>
    </nav>
  );
};

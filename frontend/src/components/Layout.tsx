import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import ImportModal from './ImportModal';

const NAV = [
  { to: '/', label: 'Dashboard', icon: DashboardIcon, end: true },
  { to: '/trades', label: 'Trades', icon: TradesIcon },
  { to: '/calendar', label: 'Calendar', icon: CalendarIcon },
  { to: '/analytics', label: 'Analytics', icon: AnalyticsIcon },
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
];

export default function Layout() {
  const [importOpen, setImportOpen] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className="flex min-h-screen bg-bg text-slate-100">
      <aside className="hidden w-60 shrink-0 border-r border-border bg-bg-900 p-4 md:flex md:flex-col">
        <div className="mb-8 flex items-center gap-2 px-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand text-white">
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 16l4-4 3 3 7-9" />
            </svg>
          </div>
          <span className="text-base font-semibold tracking-tight">Trading Journal</span>
        </div>
        <nav className="flex flex-col gap-1">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              <Icon className="h-4 w-4" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto space-y-3">
          <button
            type="button"
            className="btn btn-primary w-full justify-center"
            onClick={() => setImportOpen(true)}
          >
            Import trades
          </button>
          <div className="border-t border-border pt-3">
            <p className="px-2 text-xs text-slate-500">Signed in as</p>
            <p className="px-2 text-sm font-medium text-slate-200">{user?.username}</p>
            <button
              type="button"
              className="mt-2 w-full text-left text-xs text-slate-400 hover:text-slate-200"
              onClick={handleLogout}
            >
              Sign out
            </button>
          </div>
        </div>
      </aside>

      <main className="flex w-full min-w-0 flex-col">
        <header className="flex items-center justify-between border-b border-border bg-bg-900/60 px-6 py-3 backdrop-blur md:hidden">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-brand text-white">
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 16l4-4 3 3 7-9" />
              </svg>
            </div>
            <span className="text-sm font-semibold">Trading Journal</span>
          </div>
          <div className="flex items-center gap-2">
            <button type="button" className="btn btn-primary" onClick={() => setImportOpen(true)}>
              Import
            </button>
            <button
              type="button"
              className="text-xs text-slate-400 hover:text-slate-200"
              onClick={handleLogout}
            >
              Sign out
            </button>
          </div>
        </header>
        <nav className="flex gap-1 overflow-x-auto border-b border-border bg-bg-900/60 px-2 py-2 md:hidden">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => `nav-link whitespace-nowrap ${isActive ? 'active' : ''}`}
            >
              <Icon className="h-4 w-4" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="flex-1 px-4 py-6 md:px-8">
          <Outlet context={{ openImport: () => setImportOpen(true) }} />
        </div>
      </main>

      <ImportModal open={importOpen} onClose={() => setImportOpen(false)} />
    </div>
  );
}

type IconProps = { className?: string };

function DashboardIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z" />
    </svg>
  );
}
function TradesIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 6h18M3 12h18M3 18h18" />
    </svg>
  );
}
function CalendarIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <path d="M16 2v4M8 2v4M3 10h18" />
    </svg>
  );
}
function AnalyticsIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3v18h18" />
      <path d="M7 14l4-4 4 4 5-7" />
    </svg>
  );
}
function SettingsIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h.1a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v.1a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
    </svg>
  );
}

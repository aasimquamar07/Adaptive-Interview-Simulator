import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { DemoBanner } from "./DemoBanner";

const NAV = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/interview/new", label: "New interview" },
  { to: "/roadmap", label: "Learning roadmap" },
  { to: "/history", label: "History & progress" },
  { to: "/profile", label: "Profile & privacy" },
];

export function Logo({ to = "/" }: { to?: string }) {
  return (
    <Link to={to} className="flex items-center gap-2.5 font-display text-lg font-extrabold">
      <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden>
        <rect width="32" height="32" rx="8" fill="var(--accent)" />
        <path d="M8 11h11a5 5 0 0 1 0 10h-5l-4 3v-3H8z" fill="var(--accent-ink)" />
        <circle cx="23" cy="16" r="2" fill="var(--accent)" />
      </svg>
      Interview Room
    </Link>
  );
}

export function AppShell() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const linkCls = ({ isActive }: { isActive: boolean }) =>
    `block rounded-lg px-3 py-2 font-bold transition-colors ${isActive ? "bg-accent-soft text-accent" : "text-muted hover:bg-surface-2 hover:text-ink"}`;

  return (
    <div className="min-h-screen">
      <DemoBanner compact />
      <div className="mx-auto flex max-w-6xl gap-8 px-4 lg:px-6">
        <aside className="sticky top-0 hidden h-screen w-56 shrink-0 flex-col py-6 lg:flex">
          <Logo to="/dashboard" />
          <nav className="mt-8 space-y-1" aria-label="Main">
            {NAV.map((n) => <NavLink key={n.to} to={n.to} className={linkCls}>{n.label}</NavLink>)}
          </nav>
          <div className="mt-auto border-t border-line pt-4 text-sm">
            <p className="truncate font-bold">{user?.full_name || "Candidate"}</p>
            <p className="truncate text-muted">{user?.email}</p>
            <button onClick={() => { logout(); nav("/"); }} className="mt-2 text-muted underline underline-offset-2 hover:text-ink">Sign out</button>
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <header className="flex items-center justify-between py-4 lg:hidden">
            <Logo to="/dashboard" />
            <button onClick={() => setOpen(!open)} aria-expanded={open} aria-controls="mobile-nav"
                    className="rounded-lg border border-line px-3 py-1.5 font-bold">Menu</button>
          </header>
          {open && (
            <nav id="mobile-nav" className="mb-4 space-y-1 rounded-xl border border-line bg-surface p-2 lg:hidden" aria-label="Main">
              {NAV.map((n) => <NavLink key={n.to} to={n.to} className={linkCls} onClick={() => setOpen(false)}>{n.label}</NavLink>)}
              <button onClick={() => { logout(); nav("/"); }} className="block w-full rounded-lg px-3 py-2 text-left font-bold text-muted">Sign out</button>
            </nav>
          )}
          <main className="pb-16 lg:py-8"><Outlet /></main>
        </div>
      </div>
    </div>
  );
}

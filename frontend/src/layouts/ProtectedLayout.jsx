import { Dialog, Transition } from "@headlessui/react";
import {
  LayoutDashboard,
  LogOut,
  Menu,
  Shield,
  Upload,
  Users,
  X
} from "lucide-react";
import { Fragment, useEffect, useMemo, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import {
  LAST_AUDIT_STORAGE_KEY,
  USER_EMAIL_STORAGE_KEY,
  clearSession
} from "../api/fairlensApi";

const navLinkBase =
  "group flex items-center gap-3 rounded-2xl border-l-4 px-4 py-3 text-sm font-medium transition";

function ProtectedLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const userEmail = localStorage.getItem(USER_EMAIL_STORAGE_KEY) || "team@fairflow.ai";
  const latestAuditId = localStorage.getItem(LAST_AUDIT_STORAGE_KEY);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const navItems = useMemo(
    () => [
      { label: "Dashboard", to: "/dashboard", icon: LayoutDashboard },
      { label: "Upload Audit", to: "/audit", icon: Upload },
      {
        label: "Candidates",
        to: latestAuditId ? `/candidates/${latestAuditId}` : "/audit",
        icon: Users
      },
      {
        label: "Mitigation",
        to: latestAuditId ? `/mitigate/${latestAuditId}` : "/audit",
        icon: Shield
      }
    ],
    [latestAuditId]
  );

  const handleLogout = () => {
    clearSession();
    navigate("/login", { replace: true });
  };

  const sidebarContent = (
    <div className="flex h-full flex-col bg-navy text-white">
      <div className="border-b border-white/10 px-6 py-6">
        <div className="inline-flex items-center rounded-full bg-amber/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-amber-light">
          Hiring Fairness
        </div>
        <h1 className="mt-4 text-2xl font-extrabold tracking-tight">FairFlow AI</h1>
        <p className="mt-2 text-sm text-slate-300">
          Audit, explain, and mitigate bias across hiring decisions.
        </p>
      </div>

      <nav className="flex-1 space-y-2 px-4 py-6">
        {navItems.map(({ label, to, icon: Icon }) => (
          <NavLink
            key={label}
            to={to}
            className={({ isActive }) =>
              `${navLinkBase} ${
                isActive
                  ? "border-amber bg-white/5 text-amber-light"
                  : "border-transparent text-slate-300 hover:border-amber/40 hover:bg-white/5 hover:text-white"
              }`
            }
          >
            <Icon className="h-5 w-5" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-white/10 px-4 py-5">
        <div className="rounded-2xl bg-white/5 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Signed In</p>
          <p className="mt-2 truncate text-sm font-medium text-white">{userEmail}</p>
          <button
            type="button"
            onClick={handleLogout}
            className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-white/10 px-4 py-3 text-sm font-medium text-slate-100 transition hover:border-amber/40 hover:bg-amber/10 hover:text-amber-light"
          >
            <LogOut className="h-4 w-4" />
            Logout
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-100">
      <Transition.Root show={mobileOpen} as={Fragment}>
        <Dialog as="div" className="relative z-50 lg:hidden" onClose={setMobileOpen}>
          <Transition.Child
            as={Fragment}
            enter="transition-opacity duration-200"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="transition-opacity duration-150"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm" />
          </Transition.Child>
          <div className="fixed inset-0 flex">
            <Transition.Child
              as={Fragment}
              enter="transform transition duration-300"
              enterFrom="-translate-x-full"
              enterTo="translate-x-0"
              leave="transform transition duration-200"
              leaveFrom="translate-x-0"
              leaveTo="-translate-x-full"
            >
              <Dialog.Panel className="relative flex w-80 max-w-[85vw] flex-col">
                {sidebarContent}
                <button
                  type="button"
                  onClick={() => setMobileOpen(false)}
                  className="absolute right-4 top-4 rounded-full bg-white/10 p-2 text-white"
                >
                  <X className="h-5 w-5" />
                </button>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </Dialog>
      </Transition.Root>

      <div className="flex min-h-screen">
        <aside className="hidden w-80 lg:block">{sidebarContent}</aside>

        <div className="flex min-h-screen min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/80 backdrop-blur">
            <div className="flex items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setMobileOpen(true)}
                  className="inline-flex rounded-2xl border border-slate-200 bg-white p-2 text-slate-700 shadow-sm lg:hidden"
                >
                  <Menu className="h-5 w-5" />
                </button>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                    Bias Detection Workspace
                  </p>
                  <h2 className="text-lg font-bold text-slate-900">
                    {location.pathname === "/dashboard" ? "Executive Dashboard" : "Fairness Operations"}
                  </h2>
                </div>
              </div>
              <div className="hidden rounded-full border border-amber/30 bg-amber/10 px-4 py-2 text-sm font-medium text-amber-dark sm:block">
                Live on localhost:3000
              </div>
            </div>
          </header>

          <main className="flex-1 bg-slate-50 px-4 py-6 sm:px-6 lg:px-8">
            <div className="mx-auto max-w-7xl">
              <Outlet />
            </div>
          </main>

          <footer className="border-t border-slate-200 bg-white/90 px-4 py-4 sm:px-6 lg:px-8">
            <div className="mx-auto flex max-w-7xl flex-col gap-3 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
              <p>FairLens AI • Glass Box Fairness Governance</p>
              <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 font-semibold uppercase tracking-[0.14em] text-indigo-700">
                Powered by IndiCASA
              </div>
            </div>
          </footer>
        </div>
      </div>
    </div>
  );
}

export default ProtectedLayout;

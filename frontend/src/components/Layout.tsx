import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

function cx(...classes: Array<string | false | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

const linkBase = "rounded-md px-3 py-2 text-sm font-medium transition-colors";

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-full">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <span className="text-lg font-semibold text-slate-900">Atos Oficiais</span>
            <span className="hidden text-sm text-slate-500 sm:inline">Extração estruturada com IA</span>
          </div>
          <nav className="flex gap-1">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                cx(linkBase, isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100")
              }
            >
              Enviar ato
            </NavLink>
            <NavLink
              to="/atos"
              className={({ isActive }) =>
                cx(linkBase, isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100")
              }
            >
              Atos processados
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  );
}

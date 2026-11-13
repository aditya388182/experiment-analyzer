import { NavLink, Outlet } from "react-router";

const LINKS = [
  { to: "/", label: "Home", end: true },
  { to: "/new", label: "Upload" },
  { to: "/sample-size", label: "Sample size" },
  { to: "/reports", label: "Model reports" },
  { to: "/method", label: "Method" },
];

export function Layout() {
  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:bg-white focus:p-2">
        Skip to content
      </a>
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <NavLink to="/" className="text-lg font-semibold tracking-tight text-teal-800">
            Experiment Analyzer
          </NavLink>
          <nav aria-label="Main">
            <ul className="flex flex-wrap gap-1 text-sm">
              {LINKS.map((l) => (
                <li key={l.to}>
                  <NavLink
                    to={l.to}
                    end={l.end ?? false}
                    className={({ isActive }) =>
                      `rounded-md px-3 py-1.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 ${
                        isActive ? "bg-teal-50 font-medium text-teal-900" : "text-stone-700 hover:bg-stone-100"
                      }`
                    }
                  >
                    {l.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-5xl px-4 py-8">
        <Outlet />
      </main>
      <footer className="mx-auto max-w-5xl px-4 pb-8 text-xs text-stone-500">
        Statistics by abkit (Welch t, chi-square SRM, Holm, CUPED), matched to SciPy and statsmodels.
      </footer>
    </div>
  );
}

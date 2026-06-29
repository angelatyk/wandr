import { Link, useLocation } from 'react-router-dom'

const NAV_LINKS = [
  { label: 'Explore', to: '/' },
  { label: 'My Trips', to: '/itinerary' },
  { label: 'Saved', to: '/verify' },
]

const MOBILE_NAV = [
  { label: 'Discover', icon: 'explore', to: '/' },
  { label: 'Planner', icon: 'map', to: '/refine' },
  { label: 'Library', icon: 'headphones', to: '/itinerary' },
  { label: 'Profile', icon: 'person', to: '#' },
]

/**
 * TopNav — fixed header shown on all primary screens.
 * Collapses to a mobile bottom bar on small viewports.
 */
export default function TopNav() {
  const { pathname } = useLocation()

  return (
    <>
      {/* ── Desktop / Tablet top bar ── */}
      <nav className="fixed top-0 w-full z-50 bg-surface/80 backdrop-blur-md">
        <div className="flex justify-between items-center px-5 md:px-16 h-20 w-full max-w-screen-2xl mx-auto">
          {/* Logo */}
          <Link
            to="/"
            className="font-display text-2xl md:text-5xl text-primary tracking-tight leading-none"
            style={{ fontFamily: 'var(--font-display)', fontWeight: 700 }}
          >
            Wandr
          </Link>

          {/* Desktop links */}
          <div className="hidden md:flex items-center gap-6">
            {NAV_LINKS.map(({ label, to }) => (
              <Link
                key={label}
                to={to}
                className={[
                  'font-label uppercase tracking-widest text-xs transition-colors duration-300',
                  pathname === to
                    ? 'text-primary border-b-2 border-secondary-container pb-0.5'
                    : 'text-on-surface-muted hover:text-primary',
                ].join(' ')}
                style={{ fontFamily: 'var(--font-body)', fontWeight: 600 }}
              >
                {label}
              </Link>
            ))}
          </div>

          {/* Icon actions */}
          <div className="flex items-center gap-2 text-primary">
            <button
              aria-label="Notifications"
              className="p-2 hover:text-secondary transition-colors duration-300 rounded-lg"
            >
              <span className="material-symbols-outlined text-[24px]">notifications</span>
            </button>
            <button
              aria-label="Account"
              className="p-2 hover:text-secondary transition-colors duration-300 rounded-lg"
            >
              <span className="material-symbols-outlined text-[24px]">account_circle</span>
            </button>
          </div>
        </div>
      </nav>

      {/* ── Mobile bottom nav ── */}
      <nav className="md:hidden fixed bottom-0 left-0 w-full z-50 flex justify-around items-center px-4 py-3 pb-safe bg-primary/90 backdrop-blur-xl rounded-t-2xl shadow-[0px_-4px_20px_rgba(10,25,47,0.10)]">
        {MOBILE_NAV.map(({ label, icon, to }) => {
          const active = to !== '#' && pathname === to
          return (
            <Link
              key={label}
              to={to}
              className={[
                'flex flex-col items-center justify-center gap-0.5 transition-all active:scale-90',
                active
                  ? 'text-secondary-container bg-white/10 rounded-xl px-4 py-1'
                  : 'text-on-primary/60 hover:text-secondary-container',
              ].join(' ')}
            >
              <span
                className="material-symbols-outlined text-[22px]"
                style={{ fontVariationSettings: active ? "'FILL' 1" : "'FILL' 0" }}
              >
                {icon}
              </span>
              <span
                className="text-[10px] leading-tight"
                style={{ fontFamily: 'var(--font-body)', fontWeight: 600, letterSpacing: '0.05em' }}
              >
                {label}
              </span>
            </Link>
          )
        })}
      </nav>
    </>
  )
}

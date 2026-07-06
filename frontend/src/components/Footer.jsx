/**
 * Footer — shown on the home page and other marketing screens.
 * Simple three-column layout: brand, copyright, legal links.
 */
export default function Footer() {
  return (
    <footer className="w-full py-12 border-t border-outline-variant flex flex-col md:flex-row justify-between items-center px-5 md:px-16 gap-6 bg-surface-low">
      <span
        className="text-3xl md:text-5xl text-primary tracking-tight"
        style={{ fontFamily: 'var(--font-display)', fontWeight: 700 }}
      >
        Wandr
      </span>

      <p className="text-sm text-on-surface-muted text-center md:text-left" style={{ fontFamily: 'var(--font-body)' }}>
        © 2025 Wandr AI Travel. Curated for the Sophisticated Explorer.
      </p>

      <div className="flex gap-6">
        {['Terms of Service', 'Privacy Policy', 'Contact Support'].map((label) => (
          <a
            key={label}
            href="#"
            className="text-sm text-on-surface-muted hover:text-secondary transition-colors duration-300"
            style={{ fontFamily: 'var(--font-body)' }}
          >
            {label}
          </a>
        ))}
      </div>
    </footer>
  )
}

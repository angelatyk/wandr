/**
 * Footer — shown on the home page and marketing-style screens.
 *
 * Three-column layout: Wandr brand wordmark, copyright line, legal links.
 * The legal links currently point to `#` as placeholders — wire them up
 * when real policy pages are available.
 */
export default function Footer() {
  return (
    <footer className="w-full py-12 border-t border-outline-variant flex flex-col md:flex-row justify-between items-center px-5 md:px-16 gap-6 bg-surface-low">
      <span
        className="text-3xl md:text-5xl text-primary tracking-tight"
        style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}
      >
        Wandr
      </span>

      <div className="flex flex-col items-center gap-1">
        <p
          className="text-sm text-on-surface-muted text-center"
          style={{ fontFamily: "var(--font-body)" }}
        >
          © 2026 Wandr AI Travel. Curated for the Sophisticated Explorer.
        </p>
        <p
          className="text-sm text-on-surface-muted text-center"
          style={{ fontFamily: "var(--font-body)" }}
        >
          Created by Team A² -{" "}
          <a
            href="https://github.com/angelatyk"
            target="_blank"
            rel="noopener noreferrer"
            className="text-secondary hover:text-primary transition-colors duration-300"
          >
            Angela
          </a>
          {" and "}
          <a
            href="https://github.com/andres-linero"
            target="_blank"
            rel="noopener noreferrer"
            className="text-secondary hover:text-primary transition-colors duration-300"
          >
            Andres
          </a>
        </p>
      </div>

      <div className="flex gap-6">
        {["Terms of Service", "Privacy Policy", "Contact Support"].map(
          (label) => (
            <a
              key={label}
              href="#"
              className="text-sm text-on-surface-muted hover:text-secondary transition-colors duration-300"
              style={{ fontFamily: "var(--font-body)" }}
            >
              {label}
            </a>
          ),
        )}
      </div>
    </footer>
  );
}

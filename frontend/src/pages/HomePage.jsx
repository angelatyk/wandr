import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import TopNav from "../components/TopNav";
import Footer from "../components/Footer";
import PersonaGrid from "../components/PersonaGrid";
import LocationAutocomplete from "../components/LocationAutocomplete";
import { PERSONAS } from "../data/mockItinerary";

// Dynamically import all images in src/assets starting with 'hero-bg'
const globImages = import.meta.glob("../assets/hero-bg*.{png,jpg,jpeg,webp}", {
  eager: true,
  import: "default",
});
const HERO_IMAGES =
  Object.values(globImages).length > 0
    ? Object.values(globImages)
    : [
        "https://lh3.googleusercontent.com/aida-public/AB6AXuBVUu8lE_xcx-lNUsttk-9gL5EVt8-wsulBwD6IImFRtCAUGpoYk2iPspkG8AcwCa9iT0quF69HvlbU6MNjY9Kcw9UXCgJZxnu9FqYFxlgblD-h1CoEKbJFp9Nm782sYjSiMia3yY4h8Jdu2ppQ8PjxxiKJ1jf8rHeZ98VDJffaNAxy3eZ9-Dc2VUJ8EpCNTuQvJm3TDOjOLvxkCxtaRpP7Y1biyvBWgMMPVlShNF4tMLJL5TzHz-V_GsASkzMlIgXYTw9Gor6mp_fx",
      ];

/**
 * HomePage — Wandr onboarding.
 *
 * Screens covered:
 *   1. Hero section with cinematic travel image + quick-wander input
 *   2. Persona selection grid
 */
export default function HomePage() {
  const navigate = useNavigate();

  const [vibe, setVibe] = useState("");
  const [currentLocation, setCurrentLocation] = useState("");
  const [destination, setDestination] = useState("");
  const [duration, setDuration] = useState("");
  const [selectedPersona, setSelectedPersona] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [currentBgIndex, setCurrentBgIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentBgIndex((prev) => (prev + 1) % HERO_IMAGES.length);
    }, 6000); // Change background every 6 seconds
    return () => clearInterval(interval);
  }, []);

  const handleQuickWander = async (e) => {
    if (e && e.preventDefault) e.preventDefault();

    const hasVibe = !!vibe.trim();
    const hasStructured = !!destination.trim() && !!duration.trim();

    if (!hasVibe && !hasStructured) {
      alert(
        "Please either describe your vibe, or provide both destination and duration.",
      );
      return;
    }

    if (duration.trim()) {
      const dur = duration.trim().toLowerCase();
      // Basic check: must contain a number, or common time/date words
      const looksLikeTime =
        /\d/.test(dur) ||
        /hour|day|week|month|weekend|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec/.test(
          dur,
        );
      if (!looksLikeTime) {
        alert(
          "Please enter a clearer duration or date range (e.g., '3 days', 'weekend', 'Aug 1-5').",
        );
        return;
      }
    }

    setIsLoading(true);
    try {
      const res = await fetch("/api/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vibe,
          current_location: currentLocation,
          destination,
          duration,
          persona_type: selectedPersona,
        }),
      });
      const data = await res.json();
      if (data.plan_id) {
        navigate(`/refine?planId=${data.plan_id}`);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <TopNav />

      <main className="flex-1 pt-20 md:pt-32 pb-12 px-5 md:px-16 max-w-screen-2xl mx-auto w-full">
        {/* ── Hero ── */}
        <section className="relative min-h-[614px] md:min-h-[700px] rounded-2xl overflow-hidden mb-12 flex flex-col justify-end p-6 md:p-16">
          {/* Background image slideshow */}
          {HERO_IMAGES.map((img, index) => (
            <div
              key={index}
              className="absolute inset-0 bg-cover bg-center transition-opacity duration-1000 ease-in-out"
              style={{
                backgroundImage: `url("${img}")`,
                opacity: index === currentBgIndex ? 1 : 0,
              }}
            />
          ))}
          {/* Gradient overlay */}
          <div className="absolute inset-0 bg-gradient-to-t from-primary/80 via-primary/20 to-transparent" />

          {/* Content */}
          <div className="relative z-10 max-w-3xl">
            <h1
              className="text-4xl md:text-6xl font-bold text-white mb-3 drop-shadow-md"
              style={{
                fontFamily: "var(--font-display)",
                letterSpacing: "-0.02em",
                lineHeight: "1.1",
              }}
            >
              Your AI Travel Guide, Narrated.
            </h1>
            <p
              className="text-lg text-white/90 mb-6 max-w-xl"
              style={{ fontFamily: "var(--font-body)", lineHeight: "1.7" }}
            >
              Curated experiences for the sophisticated explorer. Discover the
              hidden stories of every city through immersive, personalized audio
              journeys.
            </p>

            {/* Quick Wander form */}
            <form
              onSubmit={handleQuickWander}
              className="glass rounded-2xl p-6 flex flex-col gap-4 max-w-2xl shadow-[var(--shadow-overlay)]"
            >
              {/* Natural language input */}
              <div className="flex flex-col gap-2">
                <label
                  htmlFor="vibe"
                  className="text-xs font-semibold uppercase tracking-widest text-on-surface-muted"
                  style={{ fontFamily: "var(--font-body)" }}
                >
                  Tell us your vibe
                </label>
                <div className="relative flex items-start bg-surface-white rounded-xl px-3 border border-transparent focus-within:border-outline-variant transition-colors overflow-hidden">
                  <span className="material-symbols-outlined text-outline ml-2 mt-4 flex-shrink-0 text-[20px]">
                    auto_awesome
                  </span>
                  <textarea
                    id="vibe"
                    rows={3}
                    placeholder="Describe your perfect trip, tell me where you want to explore, or use the fields below."
                    value={vibe}
                    onChange={(e) => setVibe(e.target.value)}
                    className="w-full bg-transparent border-none focus:outline-none text-base text-on-surface placeholder:text-outline py-4 px-3 resize-none"
                    style={{ fontFamily: "var(--font-body)" }}
                  />
                </div>
              </div>

              {/* Divider */}
              <div className="flex items-center gap-3 px-2">
                <div className="h-px flex-1 bg-outline-variant/30" />
                <span
                  className="text-[10px] font-semibold uppercase tracking-widest text-outline"
                  style={{ fontFamily: "var(--font-body)" }}
                >
                  OR
                </span>
                <div className="h-px flex-1 bg-outline-variant/30" />
              </div>

              {/* Structured fields */}
              <div className="flex flex-col md:flex-row gap-3">
                {/* Location Fields Column */}
                <div className="flex-1 flex flex-col gap-3 min-w-0">
                  <LocationAutocomplete
                    id="currentLocation"
                    placeholder="Current location (optional)"
                    value={currentLocation}
                    onChange={setCurrentLocation}
                    icon="near_me"
                  />
                  <LocationAutocomplete
                    id="destination"
                    placeholder="Destination"
                    value={destination}
                    onChange={setDestination}
                    icon="location_on"
                  />
                </div>

                {/* Duration Field Column */}
                <div className="relative flex-1 flex flex-col justify-center bg-surface-white/70 rounded-xl px-4 py-3 border border-transparent focus-within:border-outline-variant transition-colors min-w-0">
                  <label
                    htmlFor="duration"
                    className="text-sm font-medium text-on-surface-muted mb-1 flex items-start gap-2 leading-snug cursor-pointer"
                    style={{ fontFamily: "var(--font-body)" }}
                  >
                    <span className="material-symbols-outlined text-[20px] shrink-0">
                      schedule
                    </span>
                    <span>
                      Time available (e.g. 2 hours, 1 week, Aug 12-14)
                    </span>
                  </label>
                  <input
                    id="duration"
                    type="text"
                    placeholder="Type here..."
                    value={duration}
                    onChange={(e) => setDuration(e.target.value)}
                    className="w-full bg-transparent border-none focus:outline-none text-base text-on-surface placeholder:text-outline py-1 pl-[28px]"
                    style={{ fontFamily: "var(--font-body)" }}
                    autoComplete="off"
                  />
                </div>
              </div>

              {/* CTA */}
              <button
                type="submit"
                disabled={isLoading}
                className="bg-primary text-white font-semibold text-xs uppercase tracking-widest py-4 px-8 rounded-xl hover:bg-primary-tint transition-colors duration-300 active:scale-95 disabled:opacity-50 disabled:active:scale-100 w-full md:w-auto md:self-end"
                style={{ fontFamily: "var(--font-body)" }}
              >
                {isLoading ? "Starting..." : "Let's Wander"}
              </button>
            </form>
          </div>
        </section>

        {/* ── Persona Grid ── */}
        <PersonaGrid
          personas={PERSONAS}
          selectedPersona={selectedPersona}
          onSelectPersona={(id) =>
            setSelectedPersona((prev) => (prev === id ? null : id))
          }
          onContinue={handleQuickWander}
          isLoading={isLoading}
        />
      </main>

      <Footer />

      {/* Bottom nav spacer on mobile */}
      <div className="md:hidden h-20" />
    </div>
  );
}

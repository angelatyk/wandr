import { useState, useRef, useEffect } from 'react'

/**
 * AudioPlayer — glassmorphic floating bar fixed at the bottom.
 *
 * Design spec:
 * - Primary navy background at 90% opacity + backdrop blur
 * - Thin 4px progress bar: track in tertiary sand, fill in secondary gold
 * - Replay/Forward 10s controls flanking the play/pause button
 *
 * Props are fully controlled so the parent can feed real audio data
 * when the backend is connected.
 */
export default function AudioPlayer({ title, image, progressPct: initialProgress = 0 }) {
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(initialProgress)
  const intervalRef = useRef(null)

  // Simulate playback progress when playing
  useEffect(() => {
    if (playing) {
      intervalRef.current = setInterval(() => {
        setProgress((p) => Math.min(p + 0.25, 100))
      }, 300)
    } else {
      clearInterval(intervalRef.current)
    }
    return () => clearInterval(intervalRef.current)
  }, [playing])

  const handleReplay = () => setProgress((p) => Math.max(p - 10, 0))
  const handleForward = () => setProgress((p) => Math.min(p + 10, 100))

  return (
    <div className="fixed bottom-0 md:bottom-6 left-0 md:left-1/2 md:-translate-x-1/2 w-full md:w-[600px] z-[100] md:rounded-2xl overflow-hidden glass-dark shadow-[var(--shadow-audio)]">
      {/* Progress bar — 4px line */}
      <div className="w-full h-1 bg-tertiary-dim relative">
        <div
          className="absolute top-0 left-0 h-full bg-secondary transition-[width] duration-300 ease-linear"
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="flex items-center justify-between px-6 py-4">
        {/* Track info */}
        <div className="flex items-center gap-4">
          <img
            src={image}
            alt={title}
            className="w-12 h-12 rounded-xl object-cover flex-shrink-0"
          />
          <div className="flex flex-col">
            <span
              className="text-xs font-semibold uppercase tracking-widest text-secondary"
              style={{ fontFamily: 'var(--font-body)' }}
            >
              Now Playing
            </span>
            <span
              className="text-sm font-semibold text-white line-clamp-1"
              style={{ fontFamily: 'var(--font-body)' }}
            >
              {title}
            </span>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-4 text-white">
          <button
            aria-label="Replay 10 seconds"
            onClick={handleReplay}
            className="hover:text-secondary transition-colors duration-200"
          >
            <span className="material-symbols-outlined text-[22px]">replay_10</span>
          </button>

          <button
            aria-label={playing ? 'Pause' : 'Play'}
            onClick={() => setPlaying((p) => !p)}
            className="w-12 h-12 rounded-full bg-secondary text-on-secondary flex items-center justify-center hover:bg-secondary-dim transition-colors shadow-md"
          >
            <span className="material-symbols-outlined icon-filled text-[22px]">
              {playing ? 'pause' : 'play_arrow'}
            </span>
          </button>

          <button
            aria-label="Forward 10 seconds"
            onClick={handleForward}
            className="hover:text-secondary transition-colors duration-200"
          >
            <span className="material-symbols-outlined text-[22px]">forward_10</span>
          </button>
        </div>
      </div>
    </div>
  )
}

import { useState, useRef, useEffect, useCallback } from 'react'

function formatTime(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

/**
 * AudioPlayer — a bottom-bar audio player for stop narrations.
 *
 * Plays the TTS-generated narration MP3 that the backend pipeline produces
 * for each itinerary stop. Supports play/pause, ±10-second seek, a click-to-
 * seek progress bar, and a close button.
 *
 * Autoplay is attempted when a new `audioUrl` is supplied. If the browser
 * blocks autoplay (common on mobile without a prior gesture), the player
 * falls back gracefully — the user can tap play manually.
 *
 * Error handling probes the URL with a HEAD request to distinguish between
 * a 404 (audio was never saved) and a generic network/decode failure, so we
 * can surface a more actionable message to the user.
 *
 * @param {object}      props
 * @param {string}      props.title    — Display title shown in the player (e.g. "Senso-ji — Narration")
 * @param {string|null} props.image    — Thumbnail URL; falls back to a headphones icon if null
 * @param {string}      props.audioUrl — URL of the audio file (GCS signed URL or data: URI)
 * @param {function}    props.onClose  — Called when the user clicks the close button
 */
export default function AudioPlayer({ title, image, audioUrl, onClose }) {
  const audioRef = useRef(null)
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(Boolean(audioUrl))

  useEffect(() => {
    const audio = audioRef.current
    if (!audio || !audioUrl) return

    // Reset all playback state so the UI is clean for the new track
    setError(null)
    setLoading(true)
    setPlaying(false)
    setProgress(0)
    setCurrentTime(0)
    setDuration(0)

    audio.src = audioUrl
    audio.load()

    const tryAutoplay = () => {
      // audio.play() returns a Promise. Autoplay is blocked in most browsers
      // when there has been no prior user gesture on the page. We catch the
      // rejection silently so the player renders in a paused state instead
      // of throwing an unhandled rejection into the console.
      audio.play().then(() => {
        setPlaying(true)
      }).catch(() => {
        // Autoplay blocked — user can tap play.
        setPlaying(false)
      })
    }

    if (audio.readyState >= HTMLMediaElement.HAVE_METADATA) {
      tryAutoplay()
    } else {
      audio.addEventListener('loadedmetadata', tryAutoplay, { once: true })
    }
  }, [audioUrl])

  // useCallback prevents these stable handlers from being recreated on every
  // render, which would cause the <audio> element to re-attach them needlessly.
  const handleTimeUpdate = useCallback(() => {
    const audio = audioRef.current
    if (!audio || !audio.duration) return
    setCurrentTime(audio.currentTime)
    setProgress((audio.currentTime / audio.duration) * 100)
  }, [])

  const handleLoadedMetadata = useCallback(() => {
    const audio = audioRef.current
    if (!audio) return
    setDuration(audio.duration)
    setLoading(false)
  }, [])

  const handleEnded = useCallback(() => {
    setPlaying(false)
    setProgress(100)
  }, [])

  const handleAudioError = useCallback(async () => {
    setLoading(false)
    setPlaying(false)

    if (!audioUrl) {
      setError('No narration audio is available for this stop.')
      return
    }

    // Probe the URL with a HEAD request to give a more actionable error message.
    // A 404 means the TTS pipeline never saved the file; anything else is a
    // network or decoding issue on the client side.
    try {
      const res = await fetch(audioUrl, { method: 'HEAD' })
      if (res.status === 404) {
        setError('Narration audio was not saved for this stop. Try re-running the trip or check TTS API key.')
        return
      }
    } catch {
      // Ignore network probe errors — fall through to generic message.
    }

    setError('Could not load narration audio. Check your connection or TTS API configuration.')
  }, [audioUrl])

  const togglePlay = () => {
    const audio = audioRef.current
    if (!audio || !audioUrl) return

    if (playing) {
      audio.pause()
      setPlaying(false)
      return
    }

    audio.play().then(() => {
      setPlaying(true)
      setError(null)
    }).catch(() => {
      setError('Playback failed. Tap play again or check your connection.')
    })
  }

  const seekRelative = (deltaSec) => {
    const audio = audioRef.current
    if (!audio || !Number.isFinite(audio.duration)) return
    audio.currentTime = Math.min(Math.max(audio.currentTime + deltaSec, 0), audio.duration)
  }

  const handleProgressClick = (event) => {
    const audio = audioRef.current
    if (!audio || !Number.isFinite(audio.duration)) return
    const rect = event.currentTarget.getBoundingClientRect()
    const ratio = (event.clientX - rect.left) / rect.width
    audio.currentTime = ratio * audio.duration
  }

  return (
    <div className="fixed bottom-0 md:bottom-6 left-0 md:left-1/2 md:-translate-x-1/2 w-full md:w-[600px] z-[100] md:rounded-2xl overflow-hidden glass-dark shadow-[var(--shadow-audio)]">
      <audio
        ref={audioRef}
        preload="auto"
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={handleEnded}
        onError={handleAudioError}
      />

      {/* Progress bar */}
      <button
        type="button"
        aria-label="Seek narration"
        onClick={handleProgressClick}
        className="w-full h-1 bg-tertiary-dim relative block cursor-pointer"
      >
        <div
          className="absolute top-0 left-0 h-full bg-secondary transition-[width] duration-150 ease-linear"
          style={{ width: `${progress}%` }}
        />
      </button>

      <div className="flex items-center justify-between px-6 py-4 gap-4">
        <div className="flex items-center gap-4 min-w-0">
          {image ? (
            <img
              src={image}
              alt={title}
              className="w-12 h-12 rounded-xl object-cover flex-shrink-0"
            />
          ) : (
            <div className="w-12 h-12 rounded-xl bg-primary-container flex items-center justify-center flex-shrink-0">
              <span className="material-symbols-outlined text-white">headphones</span>
            </div>
          )}
          <div className="flex flex-col min-w-0">
            <span
              className="text-xs font-semibold uppercase tracking-widest text-secondary"
              style={{ fontFamily: 'var(--font-body)' }}
            >
              {loading ? 'Loading audio…' : error ? 'Audio unavailable' : 'Now Playing'}
            </span>
            <span
              className="text-sm font-semibold text-white line-clamp-1"
              style={{ fontFamily: 'var(--font-body)' }}
            >
              {title}
            </span>
            {error && (
              <span className="text-xs text-white/70 line-clamp-2" style={{ fontFamily: 'var(--font-body)' }}>
                {error}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 text-white flex-shrink-0">
          <span className="text-xs tabular-nums text-white/70 hidden sm:block" style={{ fontFamily: 'var(--font-body)' }}>
            {formatTime(currentTime)} / {formatTime(duration)}
          </span>

          <button
            aria-label="Replay 10 seconds"
            onClick={() => seekRelative(-10)}
            disabled={!audioUrl || loading}
            className="hover:text-secondary transition-colors duration-200 disabled:opacity-40"
          >
            <span className="material-symbols-outlined text-[22px]">replay_10</span>
          </button>

          <button
            aria-label={playing ? 'Pause' : 'Play'}
            onClick={togglePlay}
            disabled={!audioUrl || loading}
            className="w-12 h-12 rounded-full bg-secondary text-on-secondary flex items-center justify-center hover:bg-secondary-dim transition-colors shadow-md disabled:opacity-40"
          >
            <span className="material-symbols-outlined icon-filled text-[22px]">
              {playing ? 'pause' : 'play_arrow'}
            </span>
          </button>

          <button
            aria-label="Forward 10 seconds"
            onClick={() => seekRelative(10)}
            disabled={!audioUrl || loading}
            className="hover:text-secondary transition-colors duration-200 disabled:opacity-40"
          >
            <span className="material-symbols-outlined text-[22px]">forward_10</span>
          </button>

          {onClose && (
            <button
              aria-label="Close player"
              onClick={onClose}
              className="hover:text-secondary transition-colors duration-200"
            >
              <span className="material-symbols-outlined text-[22px]">close</span>
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

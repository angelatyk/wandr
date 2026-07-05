import { useState, useRef, useEffect, useCallback } from 'react'

function formatTime(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

/**
 * AudioPlayer — plays real narration MP3 from the backend TTS pipeline.
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

    setError(null)
    setLoading(true)
    setPlaying(false)
    setProgress(0)
    setCurrentTime(0)
    setDuration(0)

    audio.src = audioUrl
    audio.load()

    const tryAutoplay = () => {
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

  const handleAudioError = useCallback(() => {
    setLoading(false)
    setPlaying(false)
    setError('Could not load narration audio. The clip may still be generating.')
  }, [])

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

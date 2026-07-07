import { useState, useEffect, useRef } from 'react'
import { LOCATION_TEXT_MAX } from '../constants/inputLimits'

/**
 * LocationAutocomplete — a text input with a debounced Places autocomplete dropdown.
 *
 * Fetches suggestions from GET /api/places/autocomplete?query=<value> with a
 * 300ms debounce so we don't hammer the API on every keystroke.
 *
 * @param {object}   props
 * @param {string}   props.id          — HTML id for the <input> element
 * @param {string}   props.value       — controlled value
 * @param {function} props.onChange    — (value: string) => void, called on change and on selection
 * @param {string}   props.placeholder — input placeholder text
 * @param {string}   [props.icon]      — Material Symbol name for the leading icon (default: 'location_on')
 */
export default function LocationAutocomplete({ 
  id, 
  value, 
  onChange, 
  placeholder, 
  icon = "location_on" 
}) {
  const [options, setOptions] = useState([])
  const [showOptions, setShowOptions] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const timeoutRef = useRef(null)

  useEffect(() => {
    // If input is empty, clear options immediately
    if (!value.trim()) {
      setOptions([])
      return
    }

    // Debounce the API call by 300ms to avoid hammering Places on every keystroke
    if (timeoutRef.current) clearTimeout(timeoutRef.current)

    timeoutRef.current = setTimeout(async () => {
      setIsLoading(true)
      try {
        const res = await fetch(`/api/places/autocomplete?query=${encodeURIComponent(value)}`)
        const data = await res.json()
        setOptions(data.suggestions || [])
      } catch (err) {
        console.error("Autocomplete error:", err)
      } finally {
        setIsLoading(false)
      }
    }, 300)

    return () => clearTimeout(timeoutRef.current)
  }, [value])

  const handleBlur = () => {
    // Delay hiding the dropdown so that a mousedown on an option fires first.
    // Without this timeout, onBlur fires before onMouseDown and the dropdown
    // disappears before the click is registered, dropping the selection.
    setTimeout(() => setShowOptions(false), 150)
  }

  return (
    <div className="relative flex-1 flex items-center bg-surface-white/70 rounded-xl px-3 border border-transparent focus-within:border-outline-variant transition-colors min-w-0">
      <span className="material-symbols-outlined text-outline ml-2 flex-shrink-0 text-[20px]">
        {icon}
      </span>
      <input
        id={id}
        type="text"
        maxLength={LOCATION_TEXT_MAX}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setShowOptions(true)}
        onBlur={handleBlur}
        autoComplete="off"
        className="w-full bg-transparent border-none focus:outline-none text-base text-on-surface placeholder:text-outline py-3 px-3"
        style={{ fontFamily: 'var(--font-body)' }}
      />
      
      {/* Loading Indicator */}
      {isLoading && (
        <div className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      )}

      {/* Dropdown Options */}
      {showOptions && options.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-surface-white rounded-xl shadow-[var(--shadow-overlay)] border border-outline-variant/30 overflow-hidden z-30 py-1">
          {options.map((opt, i) => (
            <div
              key={i}
              className="px-5 py-3 hover:bg-secondary/10 hover:text-secondary cursor-pointer text-sm text-on-surface transition-colors truncate"
              style={{ fontFamily: 'var(--font-body)' }}
              onMouseDown={(e) => {
                // Use onMouseDown (not onClick) so the selection fires before
                // the input's onBlur dismisses the dropdown.
                e.preventDefault()
                onChange(opt)
                setShowOptions(false)
              }}
            >
              {opt}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

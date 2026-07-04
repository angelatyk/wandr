import { useState, useEffect, useRef } from 'react'

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

    // Debounce the API call by 300ms
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

  return (
    <div className="relative flex-1 flex items-center bg-surface-white/70 rounded-xl px-3 border border-transparent focus-within:border-outline-variant transition-colors min-w-0">
      <span className="material-symbols-outlined text-outline ml-2 flex-shrink-0 text-[20px]">
        {icon}
      </span>
      <input
        id={id}
        type="text"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setShowOptions(true)}
        onBlur={() => setShowOptions(false)}
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

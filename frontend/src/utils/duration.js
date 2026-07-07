/**
 * duration.js — shared duration-string parsing helpers.
 *
 * These utilities convert plain-English time strings (as produced by the
 * Itinerary agent) into numeric hour values so the VerifyPage can estimate
 * whether the user's selected stops fit within their available time.
 *
 * Keep these pure functions — no side effects, no imports from other modules.
 * They can be unit-tested in isolation without any React or browser setup.
 */

/**
 * parseDurationString
 *
 * Converts a user-supplied trip-duration string into a total number of hours.
 * Used to determine the "budget" against which selected stop times are checked.
 *
 * Examples:
 *   "4 hours"  → 4
 *   "2 days"   → 48
 *   "1 week"   → 168
 *   ""         → 0
 *
 * @param {string} str - Raw duration string from the persona / UI input.
 * @returns {number} Total hours (0 if the string is empty or unrecognised).
 */
export function parseDurationString(str) {
  if (!str) return 0
  const s = str.toLowerCase()
  const num = parseFloat(s.match(/(\d+(?:\.\d+)?)/)?.[1] || '0')
  if (s.includes('hour') || s.includes('hr')) return num
  if (s.includes('day')) return num * 24
  if (s.includes('week')) return num * 24 * 7
  return num
}

/**
 * parseSuggestedDuration
 *
 * Converts an agent-produced stop-duration string into hours.
 * When the string contains a range (e.g. "1-2 hours"), the midpoint is used.
 * Handles minute-based strings (e.g. "45 min" → 0.75).
 *
 * Examples:
 *   "1-2 hours"  → 1.5
 *   "45 min"     → 0.75
 *   "2 hours"    → 2
 *   ""           → 1.0  (conservative default)
 *
 * @param {string} str - Raw suggested_duration from the itinerary_options payload.
 * @returns {number} Duration in hours.
 */
export function parseSuggestedDuration(str) {
  if (!str) return 1.0
  const s = str.toLowerCase()

  // Minutes need to be scaled down to fractional hours
  const multiplier = s.includes('min') ? 1 / 60 : 1.0

  const matches = s.match(/(\d+(?:\.\d+)?)/g)
  if (matches) {
    if (matches.length > 1) {
      // Range like "1-2 hours" — use the midpoint
      return ((parseFloat(matches[0]) + parseFloat(matches[1])) / 2) * multiplier
    }
    return parseFloat(matches[0]) * multiplier
  }

  return 1.0
}

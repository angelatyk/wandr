/**
 * inputLimits.js — character-length caps for user-facing text fields.
 *
 * These values mirror the constants in `ai/models/input_limits.py`.
 * If you change a limit here, update the backend file too, and vice versa.
 * The backend enforces these limits at the API level; the frontend uses them
 * to set <textarea> / <input> maxLength attributes for immediate feedback.
 */

export const FREE_TEXT_MAX = 4000
export const LOCATION_TEXT_MAX = 400
export const SHORT_TEXT_MAX = 100

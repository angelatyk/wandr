/**
 * Mock itinerary data — static placeholder used throughout the UI.
 *
 * Shape mirrors what the real Wandr backend will eventually return.
 * When the API is ready, swap this import for a real fetch call.
 */

/** @type {import('./types').Persona[]} */
export const PERSONAS = [
  {
    id: 'foodie',
    label: 'Foodie',
    icon: 'restaurant',
    description: 'Culinary history, local markets, and hidden gems.',
  },
  {
    id: 'artist',
    label: 'Artist',
    icon: 'palette',
    description: 'Galleries, street art, and bohemian enclaves.',
  },
  {
    id: 'historian',
    label: 'Historian',
    icon: 'account_balance',
    description: 'Monuments, ancient ruins, and untold lore.',
  },
  {
    id: 'adventurer',
    label: 'Adventurer',
    icon: 'hiking',
    description: 'Urban exploring, trails, and active pursuits.',
  },
  {
    id: 'local-life',
    label: 'Local-life',
    icon: 'coffee',
    description: 'Neighborhood cafes, parks, and daily rhythms.',
  },
]



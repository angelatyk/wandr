/**
 * personas.js — static Wandr persona definitions.
 *
 * Each persona shapes the Itinerary and Narrator agents' behaviour:
 * it influences which stops are suggested, the tone of audio narration,
 * and the pace/budget defaults applied during profiling.
 *
 * These values are also used by the frontend Persona Grid on the home page
 * and sent to the backend as `persona_type` in the POST /api/plan request.
 *
 * Keep this in sync with the `PersonaType` Literal in `ai/models/persona.py`.
 * The id values must exactly match the backend enum strings.
 *
 * @type {{ id: string, label: string, icon: string, description: string }[]}
 */
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

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

/** @type {import('./types').Day[]} */
export const MOCK_ITINERARY = [
  {
    id: 'day-1',
    label: 'Day 1: Tsukiji & Ginza',
    stops: [
      {
        id: 'stop-1',
        name: 'Tsukiji Outer Market',
        time: '09:00 AM',
        persona: 'foodie',
        personaIcon: 'restaurant',
        description:
          'A labyrinth of narrow streets packed with stalls selling the freshest seafood, produce, and street food. Perfect for a morning grazing session.',
        badge: 'High match for culinary exploration',
        image:
          'https://lh3.googleusercontent.com/aida-public/AB6AXuBP71dHrxtfcWypdi-X6tDrlohfUJ2psOcmtyicpVQgt4QorXqIG7JbFCQjJLI1tZl433Hfl9W018UTagvluMf3snboa8G5mn7Vg-_-3Da7BEkNz-j8FcCxd8ou8dwpmXYiBUOR6JoV2vDa4vI9OukLh-YQU35DbidPEPQp2vV3qLjGdXibawrY2C4vGANTDPQkVZrQEOjJU4twyDjL9L-esVLjqLBiA3LhvRSvfoGeHmHV_Y45QrpU2EEo8XjIFg_cYkOeYWEc3wwf',
        transit: { icon: 'train', label: '10 min via Ginza Line' },
        narrationLength: '1.2 min',
        included: true,
      },
      {
        id: 'stop-2',
        name: 'Sukiyabashi Jiro Roppongi',
        time: '01:00 PM',
        persona: 'foodie',
        personaIcon: 'restaurant',
        description:
          'Experience pinnacle Edomae sushi at this legendary branch. Requires reservations well in advance, offering a masterclass in flavor and technique.',
        badge: 'Michelin-starred experience',
        image:
          'https://lh3.googleusercontent.com/aida-public/AB6AXuD-kIf4-VDNyOX5zP4DA7Rk7NowCrYcW6RrdXkLTNM7aBcrjFbqZ2ZheeDRalWjOTZk4AXhFrgt8VRrIOCXiwwf38IYMh37syIvYlpE2I60_9vsKT5jZvDiaLCVjYVomUyqiCD0ylJIoB4cFuKqZkHKEwdKSrnsTwb84hZQFJrR-fof6TdVMgb2OGXTNe8AY7a01G_6xihOuUQGRoa4DdXoTxkcpAPsQho20z_713s5XTXp8mdFWPrE08NV78W6p9RnMcG-g325dJvF',
        transit: { icon: 'directions_walk', label: '25 min walk' },
        narrationLength: '1.8 min',
        included: true,
      },
    ],
  },
  {
    id: 'day-2',
    label: 'Day 2: Shinjuku & Shibuya',
    stops: [
      {
        id: 'stop-3',
        name: 'Shinjuku Gyoen',
        time: '09:00 AM',
        persona: 'local-life',
        personaIcon: 'park',
        description:
          'Begin your day finding tranquility amidst the bustling city in one of Tokyo\'s largest and most popular parks, featuring distinct Japanese, English, and French garden styles.',
        badge: 'Peaceful morning retreat',
        image:
          'https://lh3.googleusercontent.com/aida-public/AB6AXuDFWn89vonc1w_MrdE1eRp4TM-qzh272jQJ9uSgVT-CpA9v0ozh9DrGC1KZX6PhlohO3iBf_r4DElUODOTdhzHdWKKmc876A83txOJ4Zr8np_YkVbcQ4C_s3Iw_SsbZdTdqXl2BO3arlpveVPGndUq_PeT638Yl002KijPEJ08HsrTH8xqU8NSQvicX_nwsNe1zY-KX7-tqymmirdOI7_TZd7dItBPw-uhXzRZsdA3BQlHI8XO5UZwyse_SwVDdinskwsjXQC8ShVZb',
        transit: { icon: 'train', label: '15 min via Yamanote Line' },
        narrationLength: '1.5 min',
        included: true,
      },
      {
        id: 'stop-4',
        name: 'Ichiran Shinjuku',
        time: '12:30 PM',
        persona: 'foodie',
        personaIcon: 'restaurant',
        description:
          "Experience the famous 'flavor concentration booths' designed to allow you to focus entirely on the rich, deeply satisfying tonkotsu ramen.",
        badge: 'Solo dining icon',
        image:
          'https://lh3.googleusercontent.com/aida-public/AB6AXuCKAWCMFI3EUznKFP37yYcSE9GmF-ZBqXznqzYizzteKVOBrGEn85nHEkzGgRkn-9Q1u-JJsgKbuOWOZWFf_-l9lq6QyFSmyAvdDx6IfSuORurjcyiRE9UXEQxVt2LQBummDjFMW5YlcAVieHOEL-bEn3NrRdJokiwc7BeswzM-Xvv596WbbiP3SFrLuh6Dq9w24pOfVfElVvb4k3KDzgnsLoSGmsf1O_5YTGapqJQg2sSqnCw_O4DzlFVhzUYdakgd7E6Q8_Aeh50C',
        transit: { icon: 'directions_walk', label: '20 min walk through bustling streets' },
        narrationLength: '1.0 min',
        included: true,
      },
      {
        id: 'stop-5',
        name: 'Shibuya Crossing',
        time: '04:00 PM',
        persona: 'adventurer',
        personaIcon: 'groups',
        description:
          "Stand at the heart of Tokyo's youth culture and witness the organized chaos of the world's busiest pedestrian intersection.",
        badge: 'Iconic Tokyo experience',
        image:
          'https://lh3.googleusercontent.com/aida-public/AB6AXuD5FRcyx1vnyCIoEN96jOggjUYsu_fhICtQxryYjVzJvHvCIQlbIYxOHTw05QSGOVA-7hAfR2h5KPFfFGmELGG8P4ErTF3BSeX-uu7k6vJjBUVfIioDE_KcBrviPegmfZSS3ABpHs5Mhxwrac5oJhOP-W8WnqMFQGqfl1lzMGjb8l7QlJJlw3giUkEWg8FHg7WEThsokX6W1zIcs2kPTZVq2grYittCg9JP0QB6Q0HbKJ86xPGzYoLKYdtBaMIQGWys81G0qTMXrdOA',
        transit: null,
        narrationLength: '2.0 min',
        included: true,
      },
      {
        id: 'stop-6',
        name: 'Omoide Yokocho (Memory Lane)',
        time: '07:00 PM',
        persona: 'foodie',
        personaIcon: 'restaurant',
        description:
          'Atmospheric alleyways packed with tiny yakitori joints. Great for a casual evening of skewers and drinks.',
        badge: 'Marked for removal',
        image:
          'https://lh3.googleusercontent.com/aida-public/AB6AXuBL2-0ufW-EYzRU9jtWjTUmMPeRhv1TmfC6FZv0kC8no0XjZMj4LEPRK33O7meTbwtGgKnwkZLMl5ltGm68t1v6Hyu91q2gBYM3BV3ajBGwsbyMZNMnUUB5sCscob1cQp_5FEFUhUOJWhA-cGbXEyzCum8D2r0C0y3LzT4tqcnKC1DdMCW1R37q8yeSKD8O2ymgy-4E8o_ckOUZDeb-jFFgjbkdiRX_0k2sRb_jQOGi3mKscUrvRFS8KV1Oa0_K5EUNQyqXJ64AYNoN',
        transit: null,
        narrationLength: '0.8 min',
        included: false,
      },
    ],
  },
]

/** Currently playing stop (used by mock audio player) */
export const NOW_PLAYING = {
  stopId: 'stop-3',
  title: 'Shinjuku Gyoen History',
  image:
    'https://lh3.googleusercontent.com/aida-public/AB6AXuC1ukqdPPbV98LCLHXFPEEanvXLVicGXQaiaRLcTozXuBrXqFx_zugJ4bCio2YNyQT6jBq3PRBCcG-lWmNhxQHskIWR3eeisew6Ic8yZ4HI8gGJca2ofgq-gL22zKubbnSqUZnTHXf8_CfPc2nqNZzEnnj-2wOyKo4Y_lntx8JmS5HvuoYepGh4F4sI5XVN545lJLcX576nG9Q7FTzeGnausISdXojzqvikQ9q8Hv1n56qY-6PG-sW-cHChWRrAnBMMBNDI9mtwqS-V',
  progressPct: 33,
}

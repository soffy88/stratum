/**
 * The five product entry points share existing feature routes for now.
 * Keeping the contract in one place makes the navigation surface testable;
 * it does not claim that the five journeys have passed real-user validation.
 */
export const CORE_ENTRY_ROUTES = [
  { id: 'today', label: 'Today', href: '/timeline' },
  { id: 'library', label: 'Library', href: '/documents' },
  { id: 'ask', label: 'Ask', href: '/ai' },
  { id: 'learn', label: 'Learn', href: '/learning' },
  { id: 'map', label: 'Map', href: '/graph' },
] as const;

export type CoreEntryId = (typeof CORE_ENTRY_ROUTES)[number]['id'];

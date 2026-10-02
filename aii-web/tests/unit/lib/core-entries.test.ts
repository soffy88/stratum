import { describe, expect, it } from 'vitest';
import { CORE_ENTRY_ROUTES } from '@/lib/core-entries';

describe('core entry contract', () => {
  it('exposes the five product journeys on existing feature routes', () => {
    expect(CORE_ENTRY_ROUTES).toEqual([
      { id: 'today', label: 'Today', href: '/timeline' },
      { id: 'library', label: 'Library', href: '/documents' },
      { id: 'ask', label: 'Ask', href: '/ai' },
      { id: 'learn', label: 'Learn', href: '/learning' },
      { id: 'map', label: 'Map', href: '/graph' },
    ]);
  });
});

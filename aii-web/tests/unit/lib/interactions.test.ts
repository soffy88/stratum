import { describe, expect, it, vi, beforeEach } from 'vitest';
import { recordReaderAction } from '@/lib/interactions';

describe('reader interaction contract', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('posts semantic actions with an encoded content id and optional note', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ status: 'recorded', action_id: 'act-1', event_id: null }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const result = await recordReaderAction('doc/with space', 'question', '需要核对');

    expect(result).toEqual({ status: 'recorded', action_id: 'act-1', event_id: null });
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/interactions/content/doc%2Fwith%20space/actions',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ action: 'question', note: '需要核对' }),
        credentials: 'include',
      }),
    );
  });

  it('omits an empty note for important actions', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ status: 'recorded', action_id: 'act-2' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await recordReaderAction('doc-1', 'important', '  ');

    expect(JSON.parse(fetchMock.mock.calls[0]?.[1]?.body as string)).toEqual({
      action: 'important',
    });
  });
});

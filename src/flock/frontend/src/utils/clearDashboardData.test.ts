import 'fake-indexeddb/auto';
import { describe, expect, it, vi } from 'vitest';
import { indexedDBService } from '../services/indexeddb';
import { clearDashboardData } from './clearDashboardData';

describe('clearDashboardData', () => {
  it('deletes the databases before it reloads', async () => {
    vi.spyOn(console, 'log').mockImplementation(() => {});
    // The dashboard keeps its database open, which blocks a deletion
    await indexedDBService.initialize();
    localStorage.setItem('flock-flow-settings', '{}');
    const left: string[][] = [];
    const reload = vi.fn(async () => {
      left.push((await indexedDB.databases()).map((database) => database.name ?? ''));
    });

    await clearDashboardData(reload);

    expect(reload).toHaveBeenCalledOnce();
    await vi.waitFor(() => expect(left).toEqual([[]]));
    expect(localStorage.length).toBe(0);
  });
});

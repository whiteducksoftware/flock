import 'fake-indexeddb/auto';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { indexedDBService } from '../services/indexeddb';
import { useGraphStore } from '../store/graphStore';
import { useSettingsStore } from '../store/settingsStore';
import { clearDashboardData } from './clearDashboardData';

const databases = async () => (await indexedDB.databases()).map((database) => database.name ?? '');

const open = (name: string) =>
  new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open(name);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });

describe('clearDashboardData', () => {
  beforeEach(async () => {
    vi.spyOn(console, 'log').mockImplementation(() => {});
    localStorage.clear();
    // The dashboard keeps its database open
    await indexedDBService.initialize();
    useSettingsStore.getState().setEdgeType('straight');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('deletes the dashboard database and settings before it reloads', async () => {
    const left: string[][] = [];
    const reload = vi.fn(async () => {
      left.push(await databases());
    });

    await clearDashboardData(reload);

    expect(reload).toHaveBeenCalledOnce();
    await vi.waitFor(() => expect(left).toHaveLength(1));
    expect(left[0]).not.toContain('flock_dashboard_v1');
    expect(localStorage.getItem('flock-flow-settings')).toBeNull();
  });

  it('leaves the data of other apps on the same origin alone', async () => {
    (await open('another-app')).close();
    localStorage.setItem('another-app-key', 'kept');

    await clearDashboardData(() => {});

    expect(await databases()).toContain('another-app');
    expect(localStorage.getItem('another-app-key')).toBe('kept');
  });

  it('is not blocked by its own connections when the dashboard opened the database again', async () => {
    // Every mount of the saved filters initializes the database
    await Promise.all([indexedDBService.initialize(), indexedDBService.initialize()]);
    await indexedDBService.initialize();
    const onBlocked = vi.fn();
    const reload = vi.fn();

    await clearDashboardData(reload, onBlocked);

    expect(onBlocked).not.toHaveBeenCalled();
    expect(reload).toHaveBeenCalledOnce();
  });

  it('stops and says so when the database cannot be deleted', async () => {
    vi.spyOn(indexedDB, 'deleteDatabase').mockImplementation(() => {
      const request = {} as IDBOpenDBRequest;
      setTimeout(() => {
        Object.defineProperty(request, 'error', { value: new DOMException('disk full') });
        request.onerror?.(new Event('error'));
      });
      return request;
    });
    const reload = vi.fn();

    const node = { id: 'triage', type: 'agent', position: { x: 0, y: 0 }, data: {} };
    useGraphStore.setState({ nodes: [node] as never });

    await expect(clearDashboardData(reload)).rejects.toThrow('disk full');

    expect(reload).not.toHaveBeenCalled();
    // The dashboard stays as it was
    expect(useGraphStore.getState().nodes).toHaveLength(1);
    expect(localStorage.getItem('flock-flow-settings')).not.toBeNull();
  });

  it('waits for another tab to let go of the database before it reloads', async () => {
    // Another dashboard tab, which does not close on request
    const otherTab = await open('flock_dashboard_v1');
    otherTab.onversionchange = () => {};
    const reload = vi.fn();
    const onBlocked = vi.fn();

    const cleared = clearDashboardData(reload, onBlocked);
    await vi.waitFor(() => expect(onBlocked).toHaveBeenCalledOnce());
    expect(reload).not.toHaveBeenCalled();

    otherTab.close();
    await cleared;
    expect(reload).toHaveBeenCalledOnce();
  });
});

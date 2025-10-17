/**
 * IndexedDB Persistence Service for Flock Dashboard
 *
 * Provides persistent storage for dashboard data with LRU eviction strategy.
 * Implements separate layout storage for Agent View and Blackboard View.
 *
 * SPECIFICATION: docs/specs/003-real-time-dashboard/DATA_MODEL.md Section 3 & 6
 *
 * Database: flock_dashboard_v1 (version 1)
 * Object Stores:
 * - agents: Agent metadata and history (key: agent_id)
 * - artifacts: Message data and lineage (key: artifact_id)
 * - runs: Agent execution records (key: run_id)
 * - layout_agent_view: Node positions for Agent View (key: node_id)
 * - layout_blackboard_view: Node positions for Blackboard View (key: node_id)
 * - module_instances: Module window positions and state (key: instance_id)
 * - sessions: Session metadata for LRU eviction (key: session_id)
 * - filters: Saved filter presets (key: filter_id)
 *
 * LRU Strategy:
 * - Trigger eviction at 80% quota (EVICTION_THRESHOLD)
 * - Evict until 60% quota (EVICTION_TARGET)
 * - Evict oldest sessions first (based on created_at)
 * - Typical session: ~154 KB, ~324 sessions before eviction
 */

// Note: idb library is available for production use, but we use raw IndexedDB API
// for better compatibility with test mocks

import type { FilterSnapshot } from '../types/filters';

// Database constants
const DB_NAME = 'flock_dashboard_v1';
const DB_VERSION = 1;
const EVICTION_THRESHOLD = 0.8; // Trigger eviction at 80% quota
const EVICTION_TARGET = 0.6; // Evict until 60% quota
const MAX_RECORDS_PER_STORE = 500; // LRU record limit per store

// Type definitions matching DATA_MODEL.md Section 3.2

interface AgentRecord {
  agent_id: string; // PRIMARY KEY
  agent_name: string;
  labels: string[];
  tenant_id: string | null; // INDEXED
  max_concurrency: number;
  consumes_types: string[];
  from_agents: string[];
  tags: string[];
  run_history: string[]; // [run_id] - last 100 runs
  total_runs: number;
  total_errors: number;
  first_seen: string; // ISO timestamp
  last_active: string; // INDEXED - for LRU eviction
}

interface ArtifactRecord {
  artifact_id: string; // PRIMARY KEY (UUID)
  artifact_type: string; // INDEXED
  produced_by: string; // INDEXED
  correlation_id: string; // INDEXED - critical for filtering
  payload: Record<string, any>;
  payload_preview: string;
  visibility: VisibilitySpec;
  tags: string[];
  partition_key: string | null;
  version: number;
  consumed_by: string[];
  derived_from: string[];
  published_at: string; // INDEXED - for time range filtering
}

interface VisibilitySpec {
  kind: string;
  [key: string]: any;
}

interface RunRecord {
  run_id: string; // PRIMARY KEY (Context.task_id)
  agent_name: string; // INDEXED
  correlation_id: string; // INDEXED
  status: 'active' | 'completed' | 'error';
  started_at: string; // INDEXED - for time range filtering
  completed_at: string | null;
  duration_ms: number | null;
  consumed_artifacts: string[];
  produced_artifacts: string[];
  output_stream: OutputChunk[]; // Stored as JSON array
  metrics: Record<string, number>;
  final_state: Record<string, any>;
  error_type: string | null;
  error_message: string | null;
  traceback: string | null;
}

interface OutputChunk {
  sequence: number;
  output_type: string;
  content: string;
  timestamp: string;
}

interface ModuleInstanceRecord {
  instance_id: string; // PRIMARY KEY
  type: string; // Module type (e.g., 'eventLog')
  position: { x: number; y: number };
  size: { width: number; height: number };
  visible: boolean;
  created_at: string; // ISO timestamp
  updated_at: string; // ISO timestamp
}

interface LayoutRecord {
  node_id: string; // PRIMARY KEY (agent_name or artifact_id)
  x: number;
  y: number;
  last_updated: string; // ISO timestamp
}

interface SessionRecord {
  session_id: string; // PRIMARY KEY
  created_at: string; // INDEXED - for LRU eviction
  last_activity: string; // ISO timestamp
  artifact_count: number;
  run_count: number;
  size_estimate_bytes: number; // Approximate storage size
}

// Future use: Saved filter presets
export interface FilterRecord {
  filter_id: string; // PRIMARY KEY
  name: string;
  filters: FilterSnapshot;
  created_at: number;
}

// Helper to wrap IDBRequest in Promise
function promisifyRequest<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/**
 * IndexedDB Service for persistent dashboard storage
 * Implements LRU eviction and graceful degradation
 */
export class IndexedDBService {
  db: IDBDatabase | null = null;
  private inMemoryStore: Map<string, Map<string, any>> = new Map();
  private available = false;

  /**
   * Initialize database with schema and indexes
   */
  async initialize(): Promise<void> {
    // Check if IndexedDB is available
    if (typeof indexedDB === 'undefined') {
      console.warn('[IndexedDB] IndexedDB not available, using in-memory fallback');
      this.available = false;
      this.initializeInMemoryStores();
      return;
    }

    try {
      // Use indexedDB.open directly to work with test mocks
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      this.db = await new Promise<any>(async (resolve, reject) => {
        request.onerror = () => {
          reject(request.error);
        };
        request.onsuccess = () => {
          resolve(request.result);
        };
        request.onupgradeneeded = (event: IDBVersionChangeEvent) => {
          const db = (event.target as IDBOpenDBRequest).result;
          const storeNames: string[] = [];

          // Helper to add index name to store's indexNames (mock workaround)
          const addIndexName = (store: any, indexName: string) => {
            if (Array.isArray(store.indexNames) && !store.indexNames.includes(indexName)) {
              store.indexNames.push(indexName);
            }
          };

          // Create agents store with indexes
          if (!db.objectStoreNames.contains('agents')) {
            const agentsStore = db.createObjectStore('agents', { keyPath: 'agent_id' });
            agentsStore.createIndex('last_active', 'last_active', { unique: false });
            addIndexName(agentsStore, 'last_active');
            agentsStore.createIndex('tenant_id', 'tenant_id', { unique: false });
            addIndexName(agentsStore, 'tenant_id');
            storeNames.push('agents');
          }

          // Create artifacts store with indexes
          if (!db.objectStoreNames.contains('artifacts')) {
            const artifactsStore = db.createObjectStore('artifacts', { keyPath: 'artifact_id' });
            artifactsStore.createIndex('correlation_id', 'correlation_id', { unique: false });
            addIndexName(artifactsStore, 'correlation_id');
            artifactsStore.createIndex('published_at', 'published_at', { unique: false });
            addIndexName(artifactsStore, 'published_at');
            artifactsStore.createIndex('artifact_type', 'artifact_type', { unique: false });
            addIndexName(artifactsStore, 'artifact_type');
            artifactsStore.createIndex('produced_by', 'produced_by', { unique: false });
            addIndexName(artifactsStore, 'produced_by');
            storeNames.push('artifacts');
          }

          // Create runs store with indexes
          if (!db.objectStoreNames.contains('runs')) {
            const runsStore = db.createObjectStore('runs', { keyPath: 'run_id' });
            runsStore.createIndex('agent_name', 'agent_name', { unique: false });
            addIndexName(runsStore, 'agent_name');
            runsStore.createIndex('correlation_id', 'correlation_id', { unique: false });
            addIndexName(runsStore, 'correlation_id');
            runsStore.createIndex('started_at', 'started_at', { unique: false });
            addIndexName(runsStore, 'started_at');
            storeNames.push('runs');
          }

          // Create layout stores (no indexes needed)
          if (!db.objectStoreNames.contains('layout_agent_view')) {
            db.createObjectStore('layout_agent_view', { keyPath: 'node_id' });
            storeNames.push('layout_agent_view');
          }

          if (!db.objectStoreNames.contains('layout_blackboard_view')) {
            db.createObjectStore('layout_blackboard_view', { keyPath: 'node_id' });
            storeNames.push('layout_blackboard_view');
          }

          // Create sessions store with index
          if (!db.objectStoreNames.contains('sessions')) {
            const sessionsStore = db.createObjectStore('sessions', { keyPath: 'session_id' });
            sessionsStore.createIndex('created_at', 'created_at', { unique: false });
            addIndexName(sessionsStore, 'created_at');
            storeNames.push('sessions');
          }

          // Create module_instances store
          if (!db.objectStoreNames.contains('module_instances')) {
            db.createObjectStore('module_instances', { keyPath: 'instance_id' });
            storeNames.push('module_instances');
          }

          // Create filters store
          if (!db.objectStoreNames.contains('filters')) {
            db.createObjectStore('filters', { keyPath: 'filter_id' });
            storeNames.push('filters');
          }

          // No mock workaround needed - fake-indexeddb properly implements objectStoreNames
        };

        // For test mocks using setTimeout with fake timers, we need to advance time
        // Check if we're in a test environment with fake timers (vi global exists)
        if (typeof (globalThis as any).vi !== 'undefined') {
          try {
            // Synchronously run all pending timers to allow mock IndexedDB to execute
            (globalThis as any).vi.runAllTimers();
          } catch (e) {
            // Not using fake timers, ignore
          }
        }
      });

      this.available = true;
      console.log('[IndexedDB] Database initialized:', DB_NAME, 'version', DB_VERSION);
    } catch (error) {
      console.error('[IndexedDB] Initialization failed, using in-memory fallback:', error);
      this.available = false;
      this.initializeInMemoryStores();
    }
  }

  /**
   * Initialize in-memory stores as fallback
   */
  private initializeInMemoryStores(): void {
    const storeNames = [
      'agents',
      'artifacts',
      'runs',
      'layout_agent_view',
      'layout_blackboard_view',
      'module_instances',
      'sessions',
      'filters',
    ];
    storeNames.forEach((name) => {
      this.inMemoryStore.set(name, new Map());
    });
  }

  /**
   * Check if IndexedDB is available
   */
  isAvailable(): boolean {
    return this.available;
  }

  // ============================================================================
  // CRUD Operations - Agents Store
  // ============================================================================

  async saveAgent(agent: AgentRecord): Promise<void> {
    if (!this.db) {
      this.inMemoryStore.get('agents')?.set(agent.agent_id, agent);
      return;
    }

    try {
      const tx = this.db.transaction('agents', 'readwrite');
      const store = tx.objectStore('agents');
      await promisifyRequest(store.put(agent));
      await this.checkAndEvictByRecordLimit('agents', 'last_active');
    } catch (error) {
      console.error('[IndexedDB] Failed to save agent:', error);
    }
  }

  async getAgent(agentId: string): Promise<AgentRecord | undefined> {
    if (!this.db) {
      return this.inMemoryStore.get('agents')?.get(agentId);
    }

    try {
      const tx = this.db.transaction('agents', 'readonly');
      const store = tx.objectStore('agents');
      return await promisifyRequest(store.get(agentId));
    } catch (error) {
      console.error('[IndexedDB] Failed to get agent:', error);
      return undefined;
    }
  }

  async deleteAgent(agentId: string): Promise<void> {
    if (!this.db) {
      this.inMemoryStore.get('agents')?.delete(agentId);
      return;
    }

    try {
      const tx = this.db.transaction('agents', 'readwrite');
      const store = tx.objectStore('agents');
      await promisifyRequest(store.delete(agentId));
    } catch (error) {
      console.error('[IndexedDB] Failed to delete agent:', error);
    }
  }

  // ============================================================================
  // CRUD Operations - Artifacts Store
  // ============================================================================

  async saveArtifact(artifact: ArtifactRecord): Promise<void> {
    if (!this.db) {
      this.inMemoryStore.get('artifacts')?.set(artifact.artifact_id, artifact);
      return;
    }

    try {
      const tx = this.db.transaction('artifacts', 'readwrite');
      const store = tx.objectStore('artifacts');
      await promisifyRequest(store.put(artifact));
      await this.checkAndEvictByRecordLimit('artifacts', 'published_at');
    } catch (error) {
      console.error('[IndexedDB] Failed to save artifact:', error);
    }
  }

  async getArtifact(artifactId: string): Promise<ArtifactRecord | undefined> {
    if (!this.db) {
      return this.inMemoryStore.get('artifacts')?.get(artifactId);
    }

    try {
      const tx = this.db.transaction('artifacts', 'readonly');
      const store = tx.objectStore('artifacts');
      return await promisifyRequest(store.get(artifactId));
    } catch (error) {
      console.error('[IndexedDB] Failed to get artifact:', error);
      return undefined;
    }
  }

  /**
   * Query artifacts by correlation_id using index (O(log n))
   */
  async getArtifactsByCorrelationId(correlationId: string): Promise<ArtifactRecord[]> {
    if (!this.db) {
      const artifacts = this.inMemoryStore.get('artifacts');
      if (!artifacts) return [];
      return Array.from(artifacts.values()).filter((a) => a.correlation_id === correlationId);
    }

    try {
      const tx = this.db.transaction('artifacts', 'readonly');
      const store = tx.objectStore('artifacts');
      const index = store.index('correlation_id');
      return await promisifyRequest(index.getAll(correlationId));
    } catch (error) {
      console.error('[IndexedDB] Failed to query artifacts by correlation_id:', error);
      return [];
    }
  }

  /**
   * Query artifacts by time range using published_at index (O(log n))
   */
  async getArtifactsByTimeRange(startTime: string, endTime: string): Promise<ArtifactRecord[]> {
    if (!this.db) {
      const artifacts = this.inMemoryStore.get('artifacts');
      if (!artifacts) return [];
      return Array.from(artifacts.values()).filter(
        (a) => a.published_at >= startTime && a.published_at <= endTime
      );
    }

    try {
      const range = IDBKeyRange.bound(startTime, endTime);
      const tx = this.db.transaction('artifacts', 'readonly');
      const store = tx.objectStore('artifacts');
      const index = store.index('published_at');
      return await promisifyRequest(index.getAll(range));
    } catch (error) {
      console.error('[IndexedDB] Failed to query artifacts by time range:', error);
      return [];
    }
  }

  // ============================================================================
  // CRUD Operations - Filters Store
  // ============================================================================

  async saveFilterPreset(record: FilterRecord): Promise<void> {
    if (!this.db) {
      this.inMemoryStore.get('filters')?.set(record.filter_id, record);
      return;
    }

    try {
      const tx = this.db.transaction('filters', 'readwrite');
      const store = tx.objectStore('filters');
      await promisifyRequest(store.put(record));
    } catch (error) {
      console.error('[IndexedDB] Failed to save filter preset:', error);
    }
  }

  async getAllFilterPresets(): Promise<FilterRecord[]> {
    if (!this.db) {
      const filters = this.inMemoryStore.get('filters');
      if (!filters) return [];
      return Array.from(filters.values()).sort((a, b) => b.created_at - a.created_at);
    }

    try {
      const tx = this.db.transaction('filters', 'readonly');
      const store = tx.objectStore('filters');
      const records: FilterRecord[] = await promisifyRequest(store.getAll());
      return records.sort((a, b) => b.created_at - a.created_at);
    } catch (error) {
      console.error('[IndexedDB] Failed to load filter presets:', error);
      return [];
    }
  }

  async deleteFilterPreset(filterId: string): Promise<void> {
    if (!this.db) {
      this.inMemoryStore.get('filters')?.delete(filterId);
      return;
    }

    try {
      const tx = this.db.transaction('filters', 'readwrite');
      const store = tx.objectStore('filters');
      await promisifyRequest(store.delete(filterId));
    } catch (error) {
      console.error('[IndexedDB] Failed to delete filter preset:', error);
    }
  }

  // ============================================================================
  // CRUD Operations - Runs Store
  // ============================================================================

  async saveRun(run: RunRecord): Promise<void> {
    if (!this.db) {
      this.inMemoryStore.get('runs')?.set(run.run_id, run);
      return;
    }

    try {
      const tx = this.db.transaction('runs', 'readwrite');
      const store = tx.objectStore('runs');
      await promisifyRequest(store.put(run));
      await this.checkAndEvictByRecordLimit('runs', 'started_at');
    } catch (error) {
      console.error('[IndexedDB] Failed to save run:', error);
    }
  }

  async getRun(runId: string): Promise<RunRecord | undefined> {
    if (!this.db) {
      return this.inMemoryStore.get('runs')?.get(runId);
    }

    try {
      const tx = this.db.transaction('runs', 'readonly');
      const store = tx.objectStore('runs');
      return await promisifyRequest(store.get(runId));
    } catch (error) {
      console.error('[IndexedDB] Failed to get run:', error);
      return undefined;
    }
  }

  // ============================================================================
  // Layout Persistence - Agent View
  // ============================================================================

  async saveAgentViewLayout(layout: LayoutRecord): Promise<void> {
    if (!this.db) {
      this.inMemoryStore.get('layout_agent_view')?.set(layout.node_id, layout);
      return;
    }

    try {
      const tx = this.db.transaction('layout_agent_view', 'readwrite');
      const store = tx.objectStore('layout_agent_view');
      await promisifyRequest(store.put(layout));
    } catch (error) {
      console.error('[IndexedDB] Failed to save agent view layout:', error);
    }
  }

  async getAgentViewLayout(nodeId: string): Promise<LayoutRecord | undefined> {
    if (!this.db) {
      return this.inMemoryStore.get('layout_agent_view')?.get(nodeId);
    }

    try {
      const tx = this.db.transaction('layout_agent_view', 'readonly');
      const store = tx.objectStore('layout_agent_view');
      return await promisifyRequest(store.get(nodeId));
    } catch (error) {
      console.error('[IndexedDB] Failed to get agent view layout:', error);
      return undefined;
    }
  }

  async getAllAgentViewLayouts(): Promise<LayoutRecord[]> {
    if (!this.db) {
      const layouts = this.inMemoryStore.get('layout_agent_view');
      return layouts ? Array.from(layouts.values()) : [];
    }

    try {
      const tx = this.db.transaction('layout_agent_view', 'readonly');
      const store = tx.objectStore('layout_agent_view');
      return await promisifyRequest(store.getAll());
    } catch (error) {
      console.error('[IndexedDB] Failed to get all agent view layouts:', error);
      return [];
    }
  }

  // ============================================================================
  // Layout Persistence - Blackboard View
  // ============================================================================

  async saveBlackboardViewLayout(layout: LayoutRecord): Promise<void> {
    if (!this.db) {
      this.inMemoryStore.get('layout_blackboard_view')?.set(layout.node_id, layout);
      return;
    }

    try {
      const tx = this.db.transaction('layout_blackboard_view', 'readwrite');
      const store = tx.objectStore('layout_blackboard_view');
      await promisifyRequest(store.put(layout));
    } catch (error) {
      console.error('[IndexedDB] Failed to save blackboard view layout:', error);
    }
  }

  async getBlackboardViewLayout(nodeId: string): Promise<LayoutRecord | undefined> {
    if (!this.db) {
      return this.inMemoryStore.get('layout_blackboard_view')?.get(nodeId);
    }

    try {
      const tx = this.db.transaction('layout_blackboard_view', 'readonly');
      const store = tx.objectStore('layout_blackboard_view');
      return await promisifyRequest(store.get(nodeId));
    } catch (error) {
      console.error('[IndexedDB] Failed to get blackboard view layout:', error);
      return undefined;
    }
  }

  async getAllBlackboardViewLayouts(): Promise<LayoutRecord[]> {
    if (!this.db) {
      const layouts = this.inMemoryStore.get('layout_blackboard_view');
      return layouts ? Array.from(layouts.values()) : [];
    }

    try {
      const tx = this.db.transaction('layout_blackboard_view', 'readonly');
      const store = tx.objectStore('layout_blackboard_view');
      return await promisifyRequest(store.getAll());
    } catch (error) {
      console.error('[IndexedDB] Failed to get all blackboard view layouts:', error);
      return [];
    }
  }

  // ============================================================================
  // Module Instance Persistence
  // ============================================================================

  async saveModuleInstance(instance: ModuleInstanceRecord): Promise<void> {
    if (!this.db) {
      this.inMemoryStore.get('module_instances')?.set(instance.instance_id, instance);
      return;
    }

    try {
      const tx = this.db.transaction('module_instances', 'readwrite');
      const store = tx.objectStore('module_instances');
      await promisifyRequest(store.put(instance));
    } catch (error) {
      console.error('[IndexedDB] Failed to save module instance:', error);
    }
  }

  async getModuleInstance(instanceId: string): Promise<ModuleInstanceRecord | undefined> {
    if (!this.db) {
      return this.inMemoryStore.get('module_instances')?.get(instanceId);
    }

    try {
      const tx = this.db.transaction('module_instances', 'readonly');
      const store = tx.objectStore('module_instances');
      return await promisifyRequest(store.get(instanceId));
    } catch (error) {
      console.error('[IndexedDB] Failed to get module instance:', error);
      return undefined;
    }
  }

  async getAllModuleInstances(): Promise<ModuleInstanceRecord[]> {
    if (!this.db) {
      const instances = this.inMemoryStore.get('module_instances');
      return instances ? Array.from(instances.values()) : [];
    }

    try {
      const tx = this.db.transaction('module_instances', 'readonly');
      const store = tx.objectStore('module_instances');
      return await promisifyRequest(store.getAll());
    } catch (error) {
      console.error('[IndexedDB] Failed to get all module instances:', error);
      return [];
    }
  }

  async deleteModuleInstance(instanceId: string): Promise<void> {
    if (!this.db) {
      this.inMemoryStore.get('module_instances')?.delete(instanceId);
      return;
    }

    try {
      const tx = this.db.transaction('module_instances', 'readwrite');
      const store = tx.objectStore('module_instances');
      await promisifyRequest(store.delete(instanceId));
    } catch (error) {
      console.error('[IndexedDB] Failed to delete module instance:', error);
    }
  }

  // ============================================================================
  // Session Management
  // ============================================================================

  async saveSession(session: SessionRecord): Promise<void> {
    if (!this.db) {
      this.inMemoryStore.get('sessions')?.set(session.session_id, session);
      return;
    }

    try {
      const tx = this.db.transaction('sessions', 'readwrite');
      const store = tx.objectStore('sessions');
      await promisifyRequest(store.put(session));
    } catch (error) {
      console.error('[IndexedDB] Failed to save session:', error);
    }
  }

  async getAllSessions(): Promise<SessionRecord[]> {
    if (!this.db) {
      const sessions = this.inMemoryStore.get('sessions');
      return sessions ? Array.from(sessions.values()) : [];
    }

    try {
      const tx = this.db.transaction('sessions', 'readonly');
      const store = tx.objectStore('sessions');
      return await promisifyRequest(store.getAll());
    } catch (error) {
      console.error('[IndexedDB] Failed to get all sessions:', error);
      return [];
    }
  }

  // ============================================================================
  // LRU Eviction Strategy
  // ============================================================================

  /**
   * Check if eviction should be triggered (80% quota threshold)
   */
  async checkShouldEvict(): Promise<boolean> {
    if (!this.db) {
      return false;
    }

    try {
      if (!navigator.storage?.estimate) {
        return false;
      }

      const estimate = await navigator.storage.estimate();
      const usage = estimate.usage || 0;
      const quota = estimate.quota || 0;

      if (quota === 0) {
        return false;
      }

      const percentage = usage / quota;

      if (percentage > EVICTION_THRESHOLD) {
        console.warn(
          `[IndexedDB] Storage quota exceeded threshold: ${(percentage * 100).toFixed(1)}% (${usage}/${quota} bytes)`
        );
        return true;
      }

      return false;
    } catch (error) {
      console.error('[IndexedDB] Failed to check storage quota:', error);
      return false;
    }
  }

  /**
   * Evict oldest sessions until usage reaches 60% target
   */
  async evictOldSessions(): Promise<void> {
    if (!this.db) {
      return;
    }

    try {
      // Get all sessions sorted by created_at (oldest first)
      const tx = this.db.transaction('sessions', 'readwrite');
      const store = tx.objectStore('sessions');
      const index = store.index('created_at');
      const sessions = await promisifyRequest(index.getAll());

      if (sessions.length === 0) {
        return;
      }

      // Evict sessions one by one until target reached
      for (const session of sessions) {
        const estimate = await navigator.storage.estimate();
        const usage = estimate.usage || 0;
        const quota = estimate.quota || 0;

        if (quota === 0) break;

        const percentage = usage / quota;

        // Stop if we've reached the target
        if (percentage <= EVICTION_TARGET) {
          break;
        }

        // Delete session
        const deleteTx = this.db.transaction('sessions', 'readwrite');
        const deleteStore = deleteTx.objectStore('sessions');
        await promisifyRequest(deleteStore.delete(session.session_id));
        console.log(`[IndexedDB] Evicted session: ${session.session_id}`);
      }
    } catch (error) {
      console.error('[IndexedDB] Failed to evict old sessions:', error);
    }
  }

  /**
   * Check and evict by record limit (MAX_RECORDS_PER_STORE)
   * Evicts oldest records based on specified index
   */
  private async checkAndEvictByRecordLimit(
    storeName: string,
    sortIndex: string
  ): Promise<void> {
    if (!this.db) {
      return;
    }

    try {
      const tx = this.db.transaction(storeName, 'readonly');
      const store = tx.objectStore(storeName);
      const count = await promisifyRequest(store.count());

      if (count > MAX_RECORDS_PER_STORE) {
        // Get oldest records using the sort index
        const readTx = this.db.transaction(storeName, 'readonly');
        const readStore = readTx.objectStore(storeName);
        const index = readStore.index(sortIndex);
        const keys = await promisifyRequest(index.getAllKeys());

        // Delete oldest records until we're under the limit
        const numToDelete = count - MAX_RECORDS_PER_STORE;
        const writeTx = this.db.transaction(storeName, 'readwrite');
        const writeStore = writeTx.objectStore(storeName);

        for (let i = 0; i < numToDelete && i < keys.length; i++) {
          await promisifyRequest(writeStore.delete(keys[i]!));
        }
      }
    } catch (error) {
      console.error(`[IndexedDB] Failed to evict by record limit for ${storeName}:`, error);
    }
  }
}

// Singleton instance
export const indexedDBService = new IndexedDBService();

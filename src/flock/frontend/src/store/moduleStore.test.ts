import { describe, it, expect, beforeEach } from 'vitest';
import { useModuleStore } from './moduleStore';
import type { ModuleInstance } from '../types/modules';

describe('moduleStore', () => {
  beforeEach(() => {
    // Reset store before each test
    useModuleStore.setState({
      instances: new Map(),
    });
  });

  it('should have an empty Map as initial state', () => {
    const instances = useModuleStore.getState().instances;
    expect(instances.size).toBe(0);
    expect(instances instanceof Map).toBe(true);
  });

  it('should add a new module instance', () => {
    const module: ModuleInstance = {
      id: 'module-1',
      type: 'eventlog',
      position: { x: 100, y: 100 },
      size: { width: 600, height: 400 },
      visible: true,
    };

    useModuleStore.getState().addModule(module);

    const instances = useModuleStore.getState().instances;
    expect(instances.size).toBe(1);
    expect(instances.get('module-1')).toEqual(module);
  });

  it('should add multiple module instances', () => {
    const module1: ModuleInstance = {
      id: 'module-1',
      type: 'eventlog',
      position: { x: 100, y: 100 },
      size: { width: 600, height: 400 },
      visible: true,
    };

    const module2: ModuleInstance = {
      id: 'module-2',
      type: 'eventlog',
      position: { x: 200, y: 200 },
      size: { width: 600, height: 400 },
      visible: true,
    };

    useModuleStore.getState().addModule(module1);
    useModuleStore.getState().addModule(module2);

    const instances = useModuleStore.getState().instances;
    expect(instances.size).toBe(2);
    expect(instances.get('module-1')).toEqual(module1);
    expect(instances.get('module-2')).toEqual(module2);
  });

  it('should update module position', () => {
    const module: ModuleInstance = {
      id: 'module-1',
      type: 'eventlog',
      position: { x: 100, y: 100 },
      size: { width: 600, height: 400 },
      visible: true,
    };

    useModuleStore.getState().addModule(module);
    useModuleStore.getState().updateModule('module-1', {
      position: { x: 300, y: 300 },
    });

    const updated = useModuleStore.getState().instances.get('module-1');
    expect(updated?.position).toEqual({ x: 300, y: 300 });
    expect(updated?.size).toEqual({ width: 600, height: 400 }); // Other properties unchanged
    expect(updated?.visible).toBe(true);
  });

  it('should update module size', () => {
    const module: ModuleInstance = {
      id: 'module-1',
      type: 'eventlog',
      position: { x: 100, y: 100 },
      size: { width: 600, height: 400 },
      visible: true,
    };

    useModuleStore.getState().addModule(module);
    useModuleStore.getState().updateModule('module-1', {
      size: { width: 800, height: 600 },
    });

    const updated = useModuleStore.getState().instances.get('module-1');
    expect(updated?.size).toEqual({ width: 800, height: 600 });
    expect(updated?.position).toEqual({ x: 100, y: 100 }); // Other properties unchanged
  });

  it('should update multiple module properties at once', () => {
    const module: ModuleInstance = {
      id: 'module-1',
      type: 'eventlog',
      position: { x: 100, y: 100 },
      size: { width: 600, height: 400 },
      visible: true,
    };

    useModuleStore.getState().addModule(module);
    useModuleStore.getState().updateModule('module-1', {
      position: { x: 300, y: 300 },
      size: { width: 800, height: 600 },
      visible: false,
    });

    const updated = useModuleStore.getState().instances.get('module-1');
    expect(updated?.position).toEqual({ x: 300, y: 300 });
    expect(updated?.size).toEqual({ width: 800, height: 600 });
    expect(updated?.visible).toBe(false);
  });

  it('should toggle module visibility', () => {
    const module: ModuleInstance = {
      id: 'module-1',
      type: 'eventlog',
      position: { x: 100, y: 100 },
      size: { width: 600, height: 400 },
      visible: true,
    };

    useModuleStore.getState().addModule(module);

    // Toggle visibility to false
    useModuleStore.getState().toggleVisibility('module-1');
    expect(useModuleStore.getState().instances.get('module-1')?.visible).toBe(false);

    // Toggle visibility back to true
    useModuleStore.getState().toggleVisibility('module-1');
    expect(useModuleStore.getState().instances.get('module-1')?.visible).toBe(true);
  });

  it('should remove a module instance', () => {
    const module1: ModuleInstance = {
      id: 'module-1',
      type: 'eventlog',
      position: { x: 100, y: 100 },
      size: { width: 600, height: 400 },
      visible: true,
    };

    const module2: ModuleInstance = {
      id: 'module-2',
      type: 'eventlog',
      position: { x: 200, y: 200 },
      size: { width: 600, height: 400 },
      visible: true,
    };

    useModuleStore.getState().addModule(module1);
    useModuleStore.getState().addModule(module2);

    expect(useModuleStore.getState().instances.size).toBe(2);

    useModuleStore.getState().removeModule('module-1');

    const instances = useModuleStore.getState().instances;
    expect(instances.size).toBe(1);
    expect(instances.get('module-1')).toBeUndefined();
    expect(instances.get('module-2')).toEqual(module2);
  });

  it('should get all module instances', () => {
    const module1: ModuleInstance = {
      id: 'module-1',
      type: 'eventlog',
      position: { x: 100, y: 100 },
      size: { width: 600, height: 400 },
      visible: true,
    };

    const module2: ModuleInstance = {
      id: 'module-2',
      type: 'eventlog',
      position: { x: 200, y: 200 },
      size: { width: 600, height: 400 },
      visible: false,
    };

    useModuleStore.getState().addModule(module1);
    useModuleStore.getState().addModule(module2);

    const instances = useModuleStore.getState().instances;
    const allInstances = Array.from(instances.values());

    expect(allInstances.length).toBe(2);
    expect(allInstances).toContainEqual(module1);
    expect(allInstances).toContainEqual(module2);
  });

  it('should handle updating non-existent module gracefully', () => {
    useModuleStore.getState().updateModule('non-existent', {
      position: { x: 100, y: 100 },
    });

    // Should not throw error and instances should remain empty
    expect(useModuleStore.getState().instances.size).toBe(0);
  });

  it('should handle removing non-existent module gracefully', () => {
    const module: ModuleInstance = {
      id: 'module-1',
      type: 'eventlog',
      position: { x: 100, y: 100 },
      size: { width: 600, height: 400 },
      visible: true,
    };

    useModuleStore.getState().addModule(module);
    useModuleStore.getState().removeModule('non-existent');

    // Should not affect existing modules
    expect(useModuleStore.getState().instances.size).toBe(1);
    expect(useModuleStore.getState().instances.get('module-1')).toEqual(module);
  });

  it('should handle toggling visibility of non-existent module gracefully', () => {
    useModuleStore.getState().toggleVisibility('non-existent');

    // Should not throw error
    expect(useModuleStore.getState().instances.size).toBe(0);
  });

  it('should maintain Map state immutability', () => {
    const module: ModuleInstance = {
      id: 'module-1',
      type: 'eventlog',
      position: { x: 100, y: 100 },
      size: { width: 600, height: 400 },
      visible: true,
    };

    useModuleStore.getState().addModule(module);
    const instancesBefore = useModuleStore.getState().instances;

    useModuleStore.getState().updateModule('module-1', {
      position: { x: 200, y: 200 },
    });
    const instancesAfter = useModuleStore.getState().instances;

    // New Map instance should be created (immutability)
    expect(instancesBefore).not.toBe(instancesAfter);
  });
});

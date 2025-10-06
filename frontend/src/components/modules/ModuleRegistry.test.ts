import { describe, it, expect, beforeEach, vi } from 'vitest';
import { moduleRegistry, ModuleDefinition } from './ModuleRegistry';

// Mock React component for testing
const MockComponent = () => null;

describe('ModuleRegistry', () => {
  beforeEach(() => {
    // Reset the registry before each test
    // Access the private resetInstance method through the class
    (moduleRegistry.constructor as any).resetInstance();

    // Clear console spies
    vi.clearAllMocks();
  });

  describe('Module Registration', () => {
    it('should register a new module successfully', () => {
      const consoleSpy = vi.spyOn(console, 'log');

      const module: ModuleDefinition = {
        id: 'test-module',
        name: 'Test Module',
        description: 'A test module',
        component: MockComponent,
      };

      moduleRegistry.register(module);

      const registered = moduleRegistry.get('test-module');
      expect(registered).toBeDefined();
      expect(registered?.id).toBe('test-module');
      expect(registered?.name).toBe('Test Module');
      expect(registered?.description).toBe('A test module');
      expect(consoleSpy).toHaveBeenCalledWith(
        'Module "Test Module" (test-module) registered successfully.'
      );
    });

    it('should register a module with all optional properties', () => {
      const onMountMock = vi.fn();
      const onUnmountMock = vi.fn();

      const module: ModuleDefinition = {
        id: 'full-module',
        name: 'Full Module',
        description: 'Module with all properties',
        icon: 'icon-name',
        component: MockComponent,
        onMount: onMountMock,
        onUnmount: onUnmountMock,
      };

      moduleRegistry.register(module);

      const registered = moduleRegistry.get('full-module');
      expect(registered).toBeDefined();
      expect(registered?.icon).toBe('icon-name');
      expect(registered?.onMount).toBe(onMountMock);
      expect(registered?.onUnmount).toBe(onUnmountMock);
    });

    it('should prevent duplicate registration and warn', () => {
      const consoleWarnSpy = vi.spyOn(console, 'warn');

      const module: ModuleDefinition = {
        id: 'duplicate-module',
        name: 'Duplicate Module',
        description: 'Will be registered twice',
        component: MockComponent,
      };

      moduleRegistry.register(module);
      moduleRegistry.register(module);

      expect(consoleWarnSpy).toHaveBeenCalledWith(
        'Module with id "duplicate-module" is already registered. Skipping registration.'
      );

      // Should only have one module
      const allModules = moduleRegistry.getAll();
      const duplicates = allModules.filter(m => m.id === 'duplicate-module');
      expect(duplicates).toHaveLength(1);
    });
  });

  describe('Module Retrieval', () => {
    it('should retrieve a module by ID', () => {
      const module: ModuleDefinition = {
        id: 'retrieve-test',
        name: 'Retrieve Test',
        description: 'Test retrieval',
        component: MockComponent,
      };

      moduleRegistry.register(module);
      const retrieved = moduleRegistry.get('retrieve-test');

      expect(retrieved).toBeDefined();
      expect(retrieved?.id).toBe('retrieve-test');
    });

    it('should return undefined for non-existent module', () => {
      const result = moduleRegistry.get('non-existent-module');
      expect(result).toBeUndefined();
    });

    it('should get all registered modules', () => {
      const module1: ModuleDefinition = {
        id: 'module-1',
        name: 'Module 1',
        description: 'First module',
        component: MockComponent,
      };

      const module2: ModuleDefinition = {
        id: 'module-2',
        name: 'Module 2',
        description: 'Second module',
        component: MockComponent,
      };

      const module3: ModuleDefinition = {
        id: 'module-3',
        name: 'Module 3',
        description: 'Third module',
        component: MockComponent,
      };

      moduleRegistry.register(module1);
      moduleRegistry.register(module2);
      moduleRegistry.register(module3);

      const allModules = moduleRegistry.getAll();
      expect(allModules).toHaveLength(3);
      expect(allModules.map(m => m.id)).toContain('module-1');
      expect(allModules.map(m => m.id)).toContain('module-2');
      expect(allModules.map(m => m.id)).toContain('module-3');
    });

    it('should return empty array when no modules registered', () => {
      const allModules = moduleRegistry.getAll();
      expect(allModules).toHaveLength(0);
      expect(allModules).toEqual([]);
    });
  });

  describe('Module Unregistration', () => {
    it('should unregister a module successfully', () => {
      const consoleSpy = vi.spyOn(console, 'log');

      const module: ModuleDefinition = {
        id: 'unregister-test',
        name: 'Unregister Test',
        description: 'Test unregistration',
        component: MockComponent,
      };

      moduleRegistry.register(module);
      expect(moduleRegistry.get('unregister-test')).toBeDefined();

      moduleRegistry.unregister('unregister-test');

      expect(moduleRegistry.get('unregister-test')).toBeUndefined();
      expect(consoleSpy).toHaveBeenCalledWith(
        'Module "Unregister Test" (unregister-test) unregistered successfully.'
      );
    });

    it('should handle unregistering non-existent module gracefully', () => {
      const consoleSpy = vi.spyOn(console, 'log');

      moduleRegistry.unregister('non-existent');

      // Should not throw error and should not log anything
      expect(consoleSpy).not.toHaveBeenCalled();
    });

    it('should remove module from getAll after unregistration', () => {
      const module1: ModuleDefinition = {
        id: 'module-1',
        name: 'Module 1',
        description: 'First module',
        component: MockComponent,
      };

      const module2: ModuleDefinition = {
        id: 'module-2',
        name: 'Module 2',
        description: 'Second module',
        component: MockComponent,
      };

      moduleRegistry.register(module1);
      moduleRegistry.register(module2);
      expect(moduleRegistry.getAll()).toHaveLength(2);

      moduleRegistry.unregister('module-1');

      const remaining = moduleRegistry.getAll();
      expect(remaining).toHaveLength(1);
      expect(remaining[0]?.id).toBe('module-2');
    });
  });

  describe('Singleton Pattern', () => {
    it('should maintain singleton instance across method calls', () => {
      const module1: ModuleDefinition = {
        id: 'singleton-test-1',
        name: 'Singleton Test 1',
        description: 'Test singleton behavior',
        component: MockComponent,
      };

      const module2: ModuleDefinition = {
        id: 'singleton-test-2',
        name: 'Singleton Test 2',
        description: 'Test singleton behavior',
        component: MockComponent,
      };

      moduleRegistry.register(module1);
      moduleRegistry.register(module2);

      // Should maintain state across different method calls
      const retrieved1 = moduleRegistry.get('singleton-test-1');
      const retrieved2 = moduleRegistry.get('singleton-test-2');
      const allModules = moduleRegistry.getAll();

      expect(retrieved1).toBeDefined();
      expect(retrieved2).toBeDefined();
      expect(allModules).toHaveLength(2);
    });

    it('should persist state after unregister and re-register operations', () => {
      const module1: ModuleDefinition = {
        id: 'persist-1',
        name: 'Persist 1',
        description: 'First persistent module',
        component: MockComponent,
      };

      const module2: ModuleDefinition = {
        id: 'persist-2',
        name: 'Persist 2',
        description: 'Second persistent module',
        component: MockComponent,
      };

      const module3: ModuleDefinition = {
        id: 'persist-3',
        name: 'Persist 3',
        description: 'Third persistent module',
        component: MockComponent,
      };

      // Register three modules
      moduleRegistry.register(module1);
      moduleRegistry.register(module2);
      moduleRegistry.register(module3);
      expect(moduleRegistry.getAll()).toHaveLength(3);

      // Unregister one
      moduleRegistry.unregister('persist-2');
      expect(moduleRegistry.getAll()).toHaveLength(2);

      // State should persist - the remaining modules should still be there
      expect(moduleRegistry.get('persist-1')).toBeDefined();
      expect(moduleRegistry.get('persist-2')).toBeUndefined();
      expect(moduleRegistry.get('persist-3')).toBeDefined();
    });
  });

  describe('Console Logging', () => {
    it('should log registration events with correct format', () => {
      const consoleSpy = vi.spyOn(console, 'log');

      const module: ModuleDefinition = {
        id: 'log-test',
        name: 'Log Test Module',
        description: 'Test logging',
        component: MockComponent,
      };

      moduleRegistry.register(module);

      expect(consoleSpy).toHaveBeenCalledTimes(1);
      expect(consoleSpy).toHaveBeenCalledWith(
        'Module "Log Test Module" (log-test) registered successfully.'
      );
    });

    it('should log unregistration events with correct format', () => {
      const consoleSpy = vi.spyOn(console, 'log');

      const module: ModuleDefinition = {
        id: 'unlog-test',
        name: 'Unlog Test Module',
        description: 'Test unregistration logging',
        component: MockComponent,
      };

      moduleRegistry.register(module);
      consoleSpy.mockClear(); // Clear registration log

      moduleRegistry.unregister('unlog-test');

      expect(consoleSpy).toHaveBeenCalledTimes(1);
      expect(consoleSpy).toHaveBeenCalledWith(
        'Module "Unlog Test Module" (unlog-test) unregistered successfully.'
      );
    });

    it('should warn when registering duplicate module', () => {
      const consoleWarnSpy = vi.spyOn(console, 'warn');

      const module: ModuleDefinition = {
        id: 'warn-test',
        name: 'Warn Test',
        description: 'Test warning',
        component: MockComponent,
      };

      moduleRegistry.register(module);
      moduleRegistry.register(module);

      expect(consoleWarnSpy).toHaveBeenCalledTimes(1);
      expect(consoleWarnSpy).toHaveBeenCalledWith(
        'Module with id "warn-test" is already registered. Skipping registration.'
      );
    });
  });
});

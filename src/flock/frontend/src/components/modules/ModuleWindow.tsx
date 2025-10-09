import React, { useCallback, memo } from 'react';
import { Rnd } from 'react-rnd';
import { useModuleStore } from '../../store/moduleStore';
import { moduleRegistry } from './ModuleRegistry';
import { useModules } from '../../hooks/useModules';

interface ModuleWindowProps {
  instanceId: string;
}

const ModuleWindow: React.FC<ModuleWindowProps> = memo(({ instanceId }) => {
  const instance = useModuleStore((state) => state.instances.get(instanceId));
  const updateModule = useModuleStore((state) => state.updateModule);
  const removeModule = useModuleStore((state) => state.removeModule);

  // Get module context from useModules hook
  const { context } = useModules();

  const handleClose = useCallback(() => {
    removeModule(instanceId);
  }, [instanceId, removeModule]);

  const handleMaximize = useCallback(() => {
    if (!instance) return;

    if (instance.maximized) {
      // Restore to previous size/position
      updateModule(instanceId, {
        maximized: false,
        position: instance.preMaximizePosition || instance.position,
        size: instance.preMaximizeSize || instance.size,
      });
    } else {
      // Maximize to full viewport
      updateModule(instanceId, {
        maximized: true,
        preMaximizePosition: instance.position,
        preMaximizeSize: instance.size,
        position: { x: 0, y: 0 },
        size: { width: window.innerWidth, height: window.innerHeight },
      });
    }
  }, [instanceId, instance, updateModule]);

  // Don't render if instance doesn't exist or is not visible
  if (!instance || !instance.visible) return null;

  // Get module definition from registry
  const moduleDefinition = moduleRegistry.get(instance.type);
  if (!moduleDefinition) {
    console.error(`Module definition not found for type: ${instance.type}`);
    return null;
  }

  const { position, size } = instance;
  const ModuleComponent = moduleDefinition.component;

  return (
    <Rnd
      position={position}
      size={size}
      disableDragging={instance.maximized}
      enableResizing={!instance.maximized}
      onDragStop={(_e, d) => {
        updateModule(instanceId, {
          position: { x: d.x, y: d.y },
        });
      }}
      onResizeStop={(_e, _direction, ref, _delta, position) => {
        updateModule(instanceId, {
          size: {
            width: parseInt(ref.style.width, 10),
            height: parseInt(ref.style.height, 10),
          },
          position,
        });
      }}
      minWidth={1000}
      minHeight={500}
      bounds="parent"
      dragHandleClassName="module-window-header"
      style={{
        zIndex: 1000,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          width: '100%',
          height: '100%',
          background: 'var(--color-glass-bg)',
          border: 'var(--border-width-1) solid var(--color-glass-border)',
          borderRadius: 'var(--radius-xl)',
          overflow: 'hidden',
          boxShadow: 'var(--shadow-xl)',
          backdropFilter: 'blur(var(--blur-lg))',
          WebkitBackdropFilter: 'blur(var(--blur-lg))',
        }}
      >
        {/* Header */}
        <div
          className="module-window-header"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: 'var(--space-component-md) var(--space-component-lg)',
            background: 'rgba(42, 42, 50, 0.5)',
            borderBottom: 'var(--border-width-1) solid var(--color-border-subtle)',
            cursor: instance.maximized ? 'default' : 'move',
            userSelect: 'none',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--gap-md)' }}>
            {moduleDefinition.icon && (
              <span style={{ fontSize: 16 }}>{moduleDefinition.icon}</span>
            )}
            <span
              style={{
                color: 'var(--color-text-primary)',
                fontSize: 'var(--font-size-body-sm)',
                fontWeight: 'var(--font-weight-semibold)',
                fontFamily: 'var(--font-family-sans)',
              }}
            >
              {moduleDefinition.name}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--gap-xs)' }}>
            {/* Maximize/Restore button */}
            <button
              onClick={handleMaximize}
              aria-label={instance.maximized ? 'Restore window' : 'Maximize window'}
              title={instance.maximized ? 'Restore' : 'Maximize'}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--color-text-secondary)',
                fontSize: '16px',
                cursor: 'pointer',
                padding: 'var(--spacing-1) var(--spacing-2)',
                lineHeight: 1,
                borderRadius: 'var(--radius-md)',
                transition: 'var(--transition-colors)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = 'var(--color-text-primary)';
                e.currentTarget.style.background = 'var(--color-bg-elevated)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'var(--color-text-secondary)';
                e.currentTarget.style.background = 'transparent';
              }}
            >
              {instance.maximized ? (
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <rect x="4" y="4" width="6" height="6" />
                  <path d="M2 2h4v4M12 12H8V8" />
                </svg>
              ) : (
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <rect x="2" y="2" width="10" height="10" />
                </svg>
              )}
            </button>

            {/* Close button */}
            <button
              onClick={handleClose}
              aria-label="Close window"
              title="Close"
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--color-text-secondary)',
                fontSize: 'var(--font-size-h3)',
                cursor: 'pointer',
                padding: 'var(--spacing-1) var(--spacing-2)',
                lineHeight: 1,
                borderRadius: 'var(--radius-md)',
                transition: 'var(--transition-colors)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = 'var(--color-error)';
                e.currentTarget.style.background = 'var(--color-error-bg)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'var(--color-text-secondary)';
                e.currentTarget.style.background = 'transparent';
              }}
            >
              ×
            </button>
          </div>
        </div>

        {/* Module Content */}
        <div
          style={{
            flex: 1,
            overflow: 'hidden',
            background: 'var(--color-bg-surface)',
          }}
        >
          <ModuleComponent context={context} />
        </div>
      </div>
    </Rnd>
  );
});

ModuleWindow.displayName = 'ModuleWindow';

export default ModuleWindow;

export interface ModuleInstance {
  id: string; // unique instance ID
  type: string; // module definition ID
  position: { x: number; y: number };
  size: { width: number; height: number };
  visible: boolean;
  maximized?: boolean;
  preMaximizePosition?: { x: number; y: number };
  preMaximizeSize?: { width: number; height: number };
  /** What the module searches for when it opens (the trace viewer: a correlation ID) */
  search?: string;
}

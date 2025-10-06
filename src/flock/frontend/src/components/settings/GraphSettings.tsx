/**
 * Graph Settings Tab
 *
 * Customization options for graph visualization:
 * - Edge type (bezier, straight, smoothstep)
 * - Edge stroke width
 * - Edge animation
 * - Edge labels visibility
 */

import React from 'react';
import { useSettingsStore } from '../../store/settingsStore';

const GraphSettings: React.FC = () => {
  const edgeType = useSettingsStore((state) => state.graph.edgeType);
  const edgeStrokeWidth = useSettingsStore((state) => state.graph.edgeStrokeWidth);
  const edgeAnimation = useSettingsStore((state) => state.graph.edgeAnimation);
  const showEdgeLabels = useSettingsStore((state) => state.graph.showEdgeLabels);

  const setEdgeType = useSettingsStore((state) => state.setEdgeType);
  const setEdgeStrokeWidth = useSettingsStore((state) => state.setEdgeStrokeWidth);
  const setEdgeAnimation = useSettingsStore((state) => state.setEdgeAnimation);
  const setShowEdgeLabels = useSettingsStore((state) => state.setShowEdgeLabels);

  return (
    <div>
      <div className="settings-section">
        <h3 className="settings-section-title">Edge Appearance</h3>

        <div className="settings-field">
          <label htmlFor="edge-type" className="settings-label">
            Edge Type
          </label>
          <p className="settings-description">
            Choose how connections between nodes are drawn
          </p>
          <select
            id="edge-type"
            value={edgeType}
            onChange={(e) => setEdgeType(e.target.value as typeof edgeType)}
            className="settings-select"
          >
            <option value="bezier">Bezier (Curved) - Default</option>
            <option value="smoothstep">Smooth Step</option>
            <option value="straight">Straight (90° Angles)</option>
            <option value="simplebezier">Simple Bezier</option>
          </select>
        </div>

        <div className="settings-field">
          <label htmlFor="edge-width" className="settings-label">
            Edge Stroke Width: {edgeStrokeWidth}px
          </label>
          <input
            id="edge-width"
            type="range"
            min="1"
            max="5"
            step="0.5"
            value={edgeStrokeWidth}
            onChange={(e) => setEdgeStrokeWidth(parseFloat(e.target.value))}
            className="settings-input"
          />
        </div>
      </div>

      <div className="settings-section">
        <h3 className="settings-section-title">Edge Behavior</h3>

        <div className="settings-field">
          <div className="settings-checkbox-wrapper">
            <input
              id="edge-animation"
              type="checkbox"
              checked={edgeAnimation}
              onChange={(e) => setEdgeAnimation(e.target.checked)}
              className="settings-checkbox"
            />
            <label htmlFor="edge-animation" className="settings-checkbox-label">
              Enable edge animation
            </label>
          </div>
          <p className="settings-description">
            Animate message flow along edges (may impact performance)
          </p>
        </div>

        <div className="settings-field">
          <div className="settings-checkbox-wrapper">
            <input
              id="edge-labels"
              type="checkbox"
              checked={showEdgeLabels}
              onChange={(e) => setShowEdgeLabels(e.target.checked)}
              className="settings-checkbox"
            />
            <label htmlFor="edge-labels" className="settings-checkbox-label">
              Show edge labels
            </label>
          </div>
          <p className="settings-description">
            Display correlation IDs and other metadata on edges
          </p>
        </div>
      </div>
    </div>
  );
};

export default GraphSettings;

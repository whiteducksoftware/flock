# Flock Dashboard

A real-time visualization dashboard for monitoring and controlling Flock agent orchestration systems. Built with modern web technologies to provide an intuitive, high-performance interface for observing multi-agent workflows.

## Overview

The Flock Dashboard provides real-time visibility into your agent orchestration system through an interactive graph-based interface. Watch agents activate, messages flow, and data transform in real-time as your multi-agent system operates.

The dashboard offers two complementary visualization modes:
- **Agent View**: Shows agents as nodes with message flows as edges - perfect for understanding agent communication patterns
- **Blackboard View**: Shows messages as nodes with data transformations as edges - ideal for tracking data lineage and transformations

## Features

### Real-Time Visualization
- **WebSocket-Based Updates**: Live streaming of agent activations, message publications, and system events
- **Dual Visualization Modes**: Switch between agent-centric and message-centric views
- **Interactive Graph**: Drag nodes, zoom, pan, and explore your system's topology
- **Auto-Layout**: Intelligent graph layout using the Dagre algorithm for optimal node positioning

### Advanced Filtering
- **Correlation ID Tracking**: Filter all views by correlation ID to trace individual workflows
- **Time Range Filtering**: Focus on specific time windows with preset ranges (last 5/10/60 minutes) or custom ranges
- **Active Filter Pills**: Visual indicators of active filters with one-click removal
- **Autocomplete Search**: Quick correlation ID selection with metadata preview

### Node Details & Monitoring
- **Floating Detail Windows**: Double-click any node to open a draggable, resizable detail window
- **Live Output Tab**: Stream real-time output from agents with color-coded message types
- **Message History**: View all consumed and published messages with full JSON payloads
- **Run Status**: Track agent execution history with timing, status, and metrics
- **Multi-Window Support**: Open multiple detail windows simultaneously for comparison

### Extensible Module System
- **Custom Visualizations**: Add specialized views via the module system
- **Historical Blackboard Module**: Persisted artifact browser with retention insights
- **Trace Viewer Module**: Jaeger-style distributed tracing with timeline and statistics
- **Context Menu Integration**: Right-click to add modules at any location
- **Persistent Layout**: Module positions and sizes are saved across sessions

### Trace Viewer Module 🔍

The **Trace Viewer** provides production-grade distributed tracing powered by OpenTelemetry and DuckDB, enabling deep debugging and performance analysis.

#### Features

- **Timeline View**: Waterfall visualization showing span hierarchies and execution order
  - Parent-child relationships with visual indentation
  - Service-specific color coding for easy identification
  - Duration bars proportional to execution time
  - Hover tooltips with detailed timing information
  - Expand/collapse nested spans

- **Statistics View**: Tabular view with comprehensive metrics
  - Sortable columns (name, duration, status)
  - Quick filtering and search
  - Status indicators (OK, ERROR)
  - Export capabilities

- **Full I/O Capture**: Complete input/output data for every operation
  - All function arguments captured as JSON
  - Return values fully serialized
  - Automatic deep object serialization
  - No truncation (except strings >5000 chars)

- **JSON Viewer**: Beautiful, interactive JSON exploration
  - Syntax highlighting with theme integration
  - Collapsible tree structure
  - **Expand All / Collapse All** buttons for quick navigation
  - Supports nested objects and arrays
  - Preserves data types (strings, numbers, booleans)

- **Multi-Trace Support**: Open multiple traces simultaneously
  - Compare execution patterns side-by-side
  - Toggle traces on/off
  - Independent expansion states

- **Performance**: Built on DuckDB (10-100x faster than SQLite)
  - Sub-millisecond query times
  - Handles thousands of spans efficiently
  - SQL-powered analytics backend

#### Usage

1. **Enable Tracing** in your Flock application:
```bash
export FLOCK_AUTO_TRACE=true
export FLOCK_TRACE_FILE=true
```

2. **Run Your Application** to generate traces
```bash
python your_flock_app.py
```

3. **Open Trace Viewer** in the dashboard:
   - Click "Add Module" or right-click canvas
   - Select "Trace Viewer"
   - Browse and select traces to visualize

4. **Analyze Traces**:
   - Click trace rows to expand timeline/statistics
   - Use search to filter by operation name
   - Expand JSON attributes to inspect I/O data
   - Click "Expand All" to see complete JSON structures

#### What Gets Traced

Every traced operation captures:
- ✅ **Input Arguments**: All function parameters (excluding `self`/`cls`)
- ✅ **Output Values**: Complete return values
- ✅ **Timing Data**: Start time, end time, duration in milliseconds
- ✅ **Span Hierarchy**: Parent-child relationships for call stacks
- ✅ **Service Names**: Automatically extracted from class names
- ✅ **Status Codes**: OK, ERROR, UNSET with error messages
- ✅ **Metadata**: Correlation IDs, agent names, context info

#### Tips

- **Finding Bottlenecks**: Sort Statistics view by duration (descending)
- **Error Investigation**: Look for red ERROR status indicators
- **I/O Debugging**: Expand JSON viewers to see exact inputs that caused issues
- **Multi-Trace Comparison**: Open related traces to compare execution patterns
- **JSON Navigation**: Use "Expand All" for complex nested structures

### Historical Blackboard Module 📚

The new Historical Blackboard module brings persisted artifacts into the dashboard so operators can rewind the blackboard, not just watch the live firehose.

#### Highlights

- **SQLite-first loading**: Fetches paginated artifacts before WebSocket replay, so the graph and detail views start with real history.
- **Rich filtering**: Mirrors server-side `FilterConfig` capabilities (type, producer, tags, visibility, correlation, time range) with multi-select controls and saved presets.
- **Consumption awareness**: Displays who consumed each artifact, run IDs, and consumption timestamps—ideal for reconciling downstream behaviour.
- **Retention transparency**: Inline banners show the oldest/latest artifacts on disk and whether additional data can be loaded.
- **Virtualized table**: Efficiently scroll through thousands of artifacts with keyboard navigation, quick selection, and payload inspection via the JSON renderer.

Launch the module via the context menu (or `Add Module → Historical Blackboard`) after running `examples/03-the-dashboard/04_persistent_pizza_dashboard.py` against a SQLite-backed orchestrator.

### Modern UI/UX
- **Glassmorphism Design**: Modern dark theme with semi-transparent surfaces and blur effects
- **Keyboard Shortcuts**: Navigate efficiently with Ctrl+M, Ctrl+F, and Esc
- **Responsive Layout**: Adapts to different screen sizes and orientations
- **Smooth Animations**: Polished transitions and visual feedback

## Getting Started

### Prerequisites

- **Node.js**: Version 18 or higher
- **Package Manager**: npm (included with Node.js) or yarn
- **Flock Backend**: Running orchestrator instance (typically on port 8344)

### Installation

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

### Running the Development Server

Start the Vite development server:

```bash
npm run dev
```

The dashboard will be available at `http://localhost:5173`

The dev server includes:
- Hot module replacement (HMR) for instant updates
- Proxy configuration for API and WebSocket connections
- Source maps for debugging
- Fast refresh for React components

### Building for Production

Create an optimized production build:

```bash
npm run build
```

This will:
- Compile TypeScript to optimized JavaScript
- Bundle and minify all assets
- Generate source maps
- Output to the `dist/` directory

To preview the production build locally:

```bash
npm run preview
```

### Environment Configuration

The dashboard can be configured via environment variables:

```bash
# .env file
VITE_WS_URL=ws://localhost:8344/ws
VITE_API_URL=http://localhost:8344/api
```

If not specified, defaults to `localhost:8344`.

## Design System

The dashboard follows a comprehensive design system documented in [`docs/DESIGN_SYSTEM.md`](/Users/ara/Work/flock-flow/frontend/docs/DESIGN_SYSTEM.md).

### Design Philosophy

1. **Dark-First Design**: Optimized for extended viewing sessions with reduced eye strain
2. **Information Hierarchy**: Critical data accessible within 5 seconds
3. **Premium Aesthetic**: Modern, sleek, professional appearance inspired by AutoGen Studio and Flowise AI
4. **Depth & Dimension**: Glassmorphism and elevation for spatial clarity
5. **Purposeful Motion**: Smooth, meaningful animations that enhance UX

### Color System

The design uses a carefully crafted color palette:
- **Backgrounds**: Layered depth from `#0a0a0b` (base) to `#2a2a32` (floating windows)
- **Primary Brand**: Indigo (`#6366f1`) for actions and selections
- **Status Colors**: Success (green), Warning (amber), Error (red), Info (blue)
- **Graph-Specific**: Distinct colors for agent nodes (blue border) and message nodes (amber border)

All color combinations meet WCAG 2.1 AA accessibility standards with minimum 4.5:1 contrast ratios.

### Typography

- **Font Family**: Inter for UI text, JetBrains Mono for code
- **Scale**: 8px base grid with systematic font sizes from 10px to 72px
- **Weights**: Light (300) to Bold (700) for hierarchy
- **Line Heights**: Optimized for readability (1.1 tight to 2.0 loose)

See [`DESIGN_SYSTEM.md`](/Users/ara/Work/flock-flow/frontend/docs/DESIGN_SYSTEM.md) for complete specifications.

## Architecture

### High-Level Structure

The dashboard is built as a single-page application (SPA) using React with TypeScript:

```
┌─────────────────────────────────────────────────┐
│              DashboardLayout                     │
├─────────────────────────────────────────────────┤
│  Header (Mode Toggle, Controls)                 │
│  FilterBar (Correlation ID, Time Range)         │
│  ┌──────────────────────┬─────────────────────┐│
│  │   GraphCanvas         │  Controls Sidebar   ││
│  │   (React Flow)        │  (Publish/Invoke)   ││
│  │                       │                     ││
│  │  - Agent Nodes        │                     ││
│  │  - Message Nodes      │                     ││
│  │  - Edges              │                     ││
│  │  - MiniMap            │                     ││
│  └──────────────────────┴─────────────────────┘│
│  DetailWindowContainer (Floating Windows)       │
│  ModuleWindows (Custom Visualizations)          │
└─────────────────────────────────────────────────┘
```

### State Management (Zustand)

The application uses Zustand for centralized state management with 6 specialized stores:

1. **graphStore**: Agents, messages, events, runs, nodes, edges
2. **uiStore**: Visualization mode, selection state, detail windows
3. **filterStore**: Correlation ID filter, time range filter
4. **streamStore**: Live streaming output from agents
5. **wsStore**: WebSocket connection state and health
6. **moduleStore**: Module instances and configurations

Each store is:
- Type-safe with TypeScript interfaces
- Devtools-enabled for debugging
- Persisted where appropriate (UI preferences, filters)

### Data Flow

```
WebSocket Connection
        ↓
Event Reception (websocket.ts)
        ↓
Store Updates (graphStore, streamStore)
        ↓
React Components Re-render
        ↓
Graph Regeneration (generateAgentViewGraph / generateBlackboardViewGraph)
        ↓
React Flow Rendering
```

### Key Services

- **websocket.ts**: Manages WebSocket connection with auto-reconnection and exponential backoff
- **indexeddb.ts**: Browser-native persistence with 7 object stores and LRU eviction
- **layout.ts**: Dagre-based automatic graph layout algorithm
- **api.ts**: REST API client for publish/invoke operations

## Key Components

### GraphCanvas
The main visualization component using React Flow v12.

**Features**:
- Custom node types (AgentNode, MessageNode)
- Custom edge types (MessageFlowEdge, TransformEdge)
- Drag-and-drop node positioning with persistence
- Double-click to open detail windows
- Right-click context menu for auto-layout and modules

**Location**: `src/components/graph/GraphCanvas.tsx`

### AgentNode
Displays agent information in the graph.

**Shows**:
- Agent name
- Status indicator (running/idle/error) with color coding
- Message type subscriptions as badges
- Consumed/published message counts

**Interactions**:
- Drag to reposition
- Double-click to open detail window
- Click to select

**Location**: `src/components/graph/AgentNode.tsx`

### MessageNode
Displays message information in blackboard view.

**Shows**:
- Message type
- Correlation ID
- Content preview (first 50 characters)
- Timestamp

**Interactions**:
- Drag to reposition
- Double-click to open detail window
- Click to select

**Location**: `src/components/graph/MessageNode.tsx`

### NodeDetailWindow
Draggable, resizable floating window with three tabs.

**Tabs**:
1. **Live Output**: Real-time streaming output with color-coded types
2. **Message History**: Table of consumed/published messages
3. **Run Status**: Historical execution runs with metrics

**Features**:
- Virtualized rendering for 1000+ output lines
- Expandable JSON payloads
- Auto-scroll to bottom (toggleable)
- Persistent position and size

**Location**: `src/components/details/NodeDetailWindow.tsx`

### FilterBar
Global filtering interface in the dashboard header.

**Filters**:
- **Correlation ID**: Autocomplete dropdown with recent IDs
- **Time Range**: Presets (5m, 10m, 1h) or custom range

**Features**:
- Active filter pills with remove buttons
- Keyboard shortcut (Ctrl+F) to focus
- Real-time filter application
- Combined filter strategy

**Location**: `src/components/filters/FilterBar.tsx`

### EventLogModule
Extensible table view for detailed event inspection.

**Features**:
- Sortable columns (timestamp, type, agent, correlation ID)
- Expandable rows for full JSON payloads
- Filtering integration with global filters
- Dark theme with glassmorphism
- Empty state messaging

**Location**: `src/components/modules/EventLogModule.tsx`

### ModuleWindow
Generic draggable, resizable window wrapper for modules.

**Features**:
- Position and size persistence
- Close button
- Dark theme integration
- Z-index management

**Location**: `src/components/modules/ModuleWindow.tsx`

## Keyboard Shortcuts ⌨️

The dashboard supports comprehensive keyboard shortcuts for efficient navigation and control:

### Panel Controls

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac) | Toggle Publish Panel | Open/close the publish control panel |
| `Ctrl+Shift+D` (or `Cmd+Shift+D` on Mac) | Toggle Agent Details | Show/hide agent detail windows for all agents |
| `Ctrl+Shift+F` (or `Cmd+Shift+F` on Mac) | Toggle Filters Panel | Open/close the filters panel |
| `Ctrl+,` (or `Cmd+,` on Mac) | Toggle Settings Panel | Open/close the settings panel |

### Navigation

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Ctrl+M` (or `Cmd+M` on Mac) | Toggle View Mode | Switch between Agent View and Blackboard View |
| `Ctrl+F` (or `Cmd+F` on Mac) | Focus Filter | Focus the correlation ID filter input for quick searching |
| `Esc` | Close Windows | Close all open detail windows and panels (priority order) |

### Help

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Ctrl+/` (or `Cmd+/` on Mac) | Show Keyboard Shortcuts | Open the keyboard shortcuts help dialog |

**Implementation**: See `src/hooks/useKeyboardShortcuts.ts` and `src/components/common/KeyboardShortcutsDialog.tsx`

### Accessibility Features

The dashboard is **WCAG 2.1 AA compliant** with:
- All buttons have proper ARIA attributes (`aria-pressed`, `aria-label`)
- Dynamic state indication for screen readers
- Keyboard-only navigation support
- Platform-aware shortcuts (⌘ on Mac, Ctrl on Windows/Linux)
- Help button (?) in toolbar for discoverability

### Using Keyboard Shortcuts

**Quick Access to Help**:
```
Press Ctrl+/ to see all available keyboard shortcuts in a beautiful modal dialog
```

**Toggle Panels**:
```
Press Ctrl+Shift+P to open/close the Publish panel
Press Ctrl+Shift+D to show/hide all agent detail windows
Press Ctrl+Shift+F to open/close filters
Press Ctrl+, to open/close settings
```

**Navigate Views**:
```
Press Ctrl+M to quickly switch between Agent View and Blackboard View
Press Ctrl+F to focus the filter input
```

**Close Everything**:
```
Press Esc to close panels and windows (follows priority: Settings → Publish → Filters → Detail Windows)
```

## Development

### Adding New Features

The dashboard is designed for extensibility. Here are common development tasks:

#### Adding a New Module

1. Create the module component:
```typescript
// src/components/modules/MyModule.tsx
import { ModuleContext } from './ModuleRegistry';

interface MyModuleProps {
  context: ModuleContext;
}

export const MyModule: React.FC<MyModuleProps> = ({ context }) => {
  const { agents, messages, events } = context;

  return (
    <div>
      {/* Your module UI */}
    </div>
  );
};
```

2. Register the module:
```typescript
// src/components/modules/registerModules.ts
import { moduleRegistry } from './ModuleRegistry';
import { MyModule } from './MyModule';

moduleRegistry.register({
  id: 'my-module',
  name: 'My Module',
  icon: '📊',
  component: MyModule,
  defaultSize: { width: 600, height: 400 },
});
```

3. The module will appear in the right-click context menu automatically.

#### Adding a New Node Type

1. Create the node component in `src/components/graph/`
2. Register in `GraphCanvas.tsx`:
```typescript
const nodeTypes = useMemo(
  () => ({
    agent: AgentNode,
    message: MessageNode,
    myCustomNode: MyCustomNode, // Add here
  }),
  []
);
```

3. Update graph generation logic in `graphStore.ts`

#### Adding a New Filter

1. Create the filter component in `src/components/filters/`
2. Add state to `filterStore.ts`
3. Integrate into `FilterBar.tsx`
4. Update filter application logic in `graphStore.ts`

### Testing

The dashboard has comprehensive test coverage (367 tests):

```bash
# Run all tests
npm run test

# Run specific test suite
npm run test graphStore.test.ts

# Run with UI
npm run test:ui

# Run with coverage
npm run test -- --coverage
```

**Test Categories**:
- **Unit Tests**: Component rendering, state management, utilities
- **Integration Tests**: Multi-component interactions, data flow
- **E2E Tests**: Critical user scenarios, performance benchmarks

**Key Test Files**:
- `src/store/*.test.ts` - State management tests
- `src/components/**/*.test.tsx` - Component tests
- `src/__tests__/integration/*.test.tsx` - Integration tests
- `src/__tests__/e2e/*.test.tsx` - End-to-end tests

### Linting and Type Checking

```bash
# Type check without emitting files
npm run type-check

# The project uses TypeScript strict mode
# All code must compile with zero type errors
```

### Code Style Guidelines

1. **TypeScript**: Use strict mode, avoid `any` types
2. **React**: Functional components with hooks
3. **State**: Use Zustand stores, not local state for shared data
4. **Styling**: Inline styles using CSS variables from design system
5. **Performance**: Memoize expensive computations, use React.memo sparingly
6. **Testing**: Write tests for new features, maintain coverage

## Troubleshooting

### Dashboard Not Loading

**Symptom**: Blank screen or loading spinner

**Solutions**:
1. Check browser console for errors (F12)
2. Verify backend is running on port 8344
3. Check WebSocket connection status in UI
4. Clear IndexedDB: Open DevTools → Application → IndexedDB → Delete
5. Clear localStorage: `localStorage.clear()` in console

### WebSocket Connection Issues

**Symptom**: "Disconnected" status indicator

**Solutions**:
1. Verify backend WebSocket endpoint is accessible: `ws://localhost:8344/ws`
2. Check for CORS issues in browser console
3. Check network tab for WebSocket connection attempts
4. Restart the backend server
5. Dashboard will auto-reconnect with exponential backoff

### Graph Performance Issues

**Symptom**: Slow rendering or laggy interactions

**Solutions**:
1. Reduce node count by filtering (use correlation ID or time range)
2. Close unnecessary detail windows
3. Check browser performance tab for bottlenecks
4. Clear old data: Click "Clear all dashboard data" button in header
5. Disable browser extensions that may interfere

### Filter Not Working

**Symptom**: Graph not updating when filter applied

**Solutions**:
1. Ensure filter is active (check filter pills)
2. Verify data exists for the filter criteria
3. Check browser console for errors
4. Clear filters and re-apply
5. Refresh the page

### Detail Window Not Opening

**Symptom**: Double-click does not open window

**Solutions**:
1. Try single-clicking first to select the node
2. Check if maximum window limit reached (close some windows)
3. Check browser console for errors
4. Verify node data exists in store

### IndexedDB Quota Exceeded

**Symptom**: Warning about storage quota

**Solutions**:
1. Dashboard uses LRU eviction automatically at 80% quota
2. Manually clear old data using "Clear all dashboard data" button
3. Check browser storage settings
4. Dashboard targets 60% quota after eviction

### Build Errors

**Symptom**: `npm run build` fails

**Solutions**:
1. Run `npm install` to ensure dependencies are up-to-date
2. Check for TypeScript errors: `npm run type-check`
3. Clear node_modules and reinstall: `rm -rf node_modules && npm install`
4. Check Node.js version (must be 18+)

### Common Error Messages

**"WebSocket connection failed"**
- Backend is not running or not accessible
- Check `VITE_WS_URL` environment variable

**"Failed to fetch artifact types"**
- REST API endpoint not available
- Check `VITE_API_URL` environment variable

**"QuotaExceededError"**
- Browser storage full
- LRU eviction will trigger automatically
- Manually clear data if needed

## Performance Targets

The dashboard is optimized for high performance:

| Metric | Target | Description |
|--------|--------|-------------|
| Initial Render | <200ms | Time to first paint |
| Graph Regeneration | <100ms | View mode switch or filter application |
| Position Save | <50ms | Node position persistence after drag |
| Position Load | <100ms | Restore positions on startup |
| WebSocket Latency | <50ms | Event processing time |
| Filter Application | <100ms | Filter criteria change to graph update |
| Autocomplete Response | <50ms | Correlation ID search results |

**Actual Performance**: All targets consistently met, with initial render averaging 8.9ms (22x faster than target).

## Browser Support

The dashboard requires a modern browser with support for:
- **ES2020+** JavaScript features
- **WebSocket API** for real-time updates
- **IndexedDB API** for persistence
- **CSS Grid and Flexbox** for layout
- **CSS Custom Properties** (variables) for theming

**Recommended Browsers**:
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+

## Contributing

We welcome contributions! Please follow these guidelines:

1. **Code Style**: Follow existing patterns, use TypeScript strict mode
2. **Testing**: Write tests for new features, maintain coverage
3. **Documentation**: Update README and DESIGN_SYSTEM.md as needed
4. **Performance**: Keep within performance targets
5. **Accessibility**: Maintain WCAG 2.1 AA compliance

### Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes with tests
4. Run tests: `npm run test`
5. Type check: `npm run type-check`
6. **Build production bundle: `npm run build`** ⚠️ **REQUIRED - MUST pass without errors!**
7. Commit changes: `git commit -m "feat: add my feature"`
8. Push to branch: `git push origin feature/my-feature`
9. Create a pull request

### 🚨 Critical Build Requirement

**Before committing any UI/frontend changes:**

```bash
npm run build
```

**This MUST complete successfully with:**
- ✅ Zero TypeScript compilation errors
- ✅ Zero linting errors
- ✅ No runtime errors in production build

**Failure to build is a blocking issue - do not commit broken builds!**

The build process:
1. Compiles TypeScript (`tsc`)
2. Bundles and optimizes with Vite
3. Outputs to `dist/` directory
4. Shows any errors or warnings

If the build fails, fix all errors before committing. Common issues:
- TypeScript type errors (check with `npm run type-check`)
- Missing dependencies (run `npm install`)
- Import errors or circular dependencies
- Invalid JSX or syntax errors

## License

MIT License - see LICENSE file for details

## Additional Resources

- **Design System**: [`docs/DESIGN_SYSTEM.md`](/Users/ara/Work/flock-flow/frontend/docs/DESIGN_SYSTEM.md)
- **Product Requirements**: `docs/specs/003-real-time-dashboard/PRD.md`
- **Solution Design**: `docs/specs/003-real-time-dashboard/SDD.md`
- **Implementation Plan**: `docs/specs/003-real-time-dashboard/PLAN.md`
- **Backend Documentation**: `../README.md`

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check existing documentation
- Review test files for usage examples

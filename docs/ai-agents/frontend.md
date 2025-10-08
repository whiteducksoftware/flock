# Frontend & Dashboard Guide for AI Agents

This document covers frontend development and dashboard usage for AI agents working with Flock Flow.

## 🚀 Running the Dashboard

### Prerequisites

- **Node.js 22+** for frontend development
- **npm** or **yarn** package manager

### Quick Start

```python
import asyncio
from pydantic import BaseModel
from flock.orchestrator import Flock
from flock.registry import flock_type

# Define artifacts
@flock_type
class Idea(BaseModel):
    topic: str
    genre: str

@flock_type
class Movie(BaseModel):
    title: str
    synopsis: str

# Create orchestrator and agents
orchestrator = Flock("openai/gpt-4o")

movie = (
    orchestrator.agent("movie")
    .description("Generate movie concepts")
    .consumes(Idea)
    .publishes(Movie)
)

# 🎉 ONE LINE TO START THE DASHBOARD!
asyncio.run(orchestrator.serve(dashboard=True))
```

### What Happens

1. ✅ **Auto-Install** - Runs `npm install` if `node_modules` missing
2. ✅ **Start Services** - Launches both Python API and React dev server
3. ✅ **Open Browser** - Automatically opens http://localhost:8000
4. ✅ **Inject Collectors** - Adds event collectors to all agents
5. ✅ **Stream Events** - Real-time WebSocket connection for live updates

### Dashboard Features

**Visualization Modes:**
- **Agent View** - Nodes are agents, edges show message flows
- **Blackboard View** - Nodes are artifacts, edges show transformations

**Controls:**
- **Publish Control** - Publish artifacts with auto-filtering
- **Invoke Control** - Invoke agents by name
- **EventLog Module** - Right-click → Add Module → EventLog

**Keyboard Shortcuts:** ⌨️
- **Ctrl+Shift+P** - Toggle Publish Panel
- **Ctrl+Shift+D** - Toggle Agent Details
- **Ctrl+Shift+F** - Toggle Filters Panel
- **Ctrl+,** - Toggle Settings Panel
- **Ctrl+M** - Toggle Agent/Blackboard View
- **Ctrl+F** - Focus filter input
- **Ctrl+/** - Show keyboard shortcuts help dialog
- **Esc** - Close panels and windows

**Real-time Features:**
- **WebSocket Streaming** - Live event updates
- **Connection Status** - Visual indicator for connection state
- **Auto-Filter** - Correlation ID tracking after publish/invoke
- **Keyboard Navigation** - Full accessibility support with WCAG 2.1 AA compliance

## 📁 Frontend Development

### Structure

```
frontend/src/
├── components/
│   ├── common/          # Reusable components
│   ├── layout/          # Layout components
│   └── modules/         # Dashboard modules
├── hooks/               # Custom React hooks
├── services/            # WebSocket, API clients
├── store/               # Zustand state management
├── types/               # TypeScript type definitions
└── utils/               # Utility functions
```

### Development Commands

```bash
cd frontend

# Start development server
npm run dev

# Run tests
npm test

# Run tests with UI
npm run test:ui

# Type checking
npm run type-check

# Build for production
npm run build
```

### Key Technologies

- **React 19** - UI framework with latest features
- **TypeScript** - Type safety and better DX
- **Vite** - Fast build tool and dev server
- **Zustand** - Lightweight state management
- **React Flow** - Graph visualization library
- **Vitest** - Fast test framework
- **IndexedDB** - Client-side persistence

### Frontend Optimization

```typescript
// ✅ Use React.memo for expensive components
const ExpensiveNode = React.memo(({ data }: NodeProps) => {
  // Component implementation
});

// ✅ Use useMemo for expensive calculations
const layout = useMemo(() => {
  return calculateLayout(nodes, edges);
}, [nodes, edges]);
```

## 🛠️ Adding Dashboard Modules

### Create a New Dashboard Module

```typescript
// 1. Create module component
const MyModule: React.FC<ModuleProps> = ({ id, position }) => {
  // Module implementation
};

// 2. Register module
import { ModuleRegistry } from '../modules/ModuleRegistry';

ModuleRegistry.register({
  name: 'MyModule',
  component: MyModule,
  icon: '📊',
  defaultSize: { width: 400, height: 300 }
});

// 3. Write tests
// frontend/src/test/modules.test.tsx
```

## 🔐 Security Considerations

### API Keys

```bash
# ✅ Use environment variables
export OPENAI_API_KEY="sk-..."
export AZURE_API_KEY="..."

# ❌ Never commit API keys to git!
# Add to .gitignore:
.env
*.key
```

### Input Validation

```python
# ✅ Validate all external inputs
@flock_type
class UserInput(BaseModel):
    query: str = Field(max_length=1000)  # Prevent abuse

# ✅ Sanitize before processing
def sanitize(text: str) -> str:
    # Remove HTML, SQL injection attempts, etc.
    return text
```

---

*For dashboard architecture details, see [architecture.md](./architecture.md#3-dashboard-system-srcflockdashboard)*

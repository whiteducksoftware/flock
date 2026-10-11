import ReactDOM from 'react-dom/client';
import '@fontsource-variable/geist';
import '@fontsource-variable/geist-mono';
import App from './App';
import { applyThemeByName } from './services/themeApplicator';
import { useSettingsStore } from './store/settingsStore';
import './styles/index.css';

// Mock data removed - dashboard now starts empty and shows only real WebSocket data

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Root element not found');
}

// The stored theme, again after a reload (a terminal theme once it is loaded).
// A theme that is gone is replaced by Graphite in the settings too.
const storedTheme = useSettingsStore.getState().appearance.theme;
void applyThemeByName(storedTheme).then((applied) => {
  if (applied !== storedTheme) useSettingsStore.getState().setTheme(applied);
});

ReactDOM.createRoot(rootElement).render(<App />);

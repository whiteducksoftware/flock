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

// The stored theme, again after a reload (a terminal theme once it is loaded)
void applyThemeByName(useSettingsStore.getState().appearance.theme);

ReactDOM.createRoot(rootElement).render(<App />);

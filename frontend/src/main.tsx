import ReactDOM from 'react-dom/client';
import App from './App';
import './styles/index.css';

// Mock data removed - dashboard now starts empty and shows only real WebSocket data

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Root element not found');
}

ReactDOM.createRoot(rootElement).render(<App />);

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

const initWidget = () => {
  const containerId = 'autoupdate-agent-widget-container';
  let container = document.getElementById(containerId);
  
  if (!container) {
    container = document.createElement('div');
    container.id = containerId;
    document.body.appendChild(container);
  }

  createRoot(container).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

initWidget();

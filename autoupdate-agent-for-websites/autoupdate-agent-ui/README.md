<div align="center">
  <img src="https://regolo.ai/wp-content/uploads/2026/06/Regolo_logo_positive.png" alt="Regolo.ai Logo" width="300" />
</div>

# React + TypeScript + Vite

<div align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen.svg" alt="Build passing" />
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
</div>

<br />

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

## Come embeddare il Chat Widget su un sito web

L'interfaccia utente è stata configurata per essere compilata come un widget embeddabile. 

### 1. Build
Per generare i file necessari, esegui il comando:
```bash
npm run build
# oppure
pnpm run build
```
Questo genererà due file principali nella cartella `dist/`: `chat-widget.js` e `chat-widget.css`.

### 2. Integrazione nel sito ospite
Carica o hosta l'intera cartella `dist` (o almeno questi due file) su un tuo server o una CDN.
Poi inserisci questo snippet nell'HTML (preferibilmente prima della chiusura del tag `</body>`) del sito in cui vuoi mostrare la chat:

```html
<!-- Sostituisci TUO_DOMINIO con l'URL effettivo dove hai esposto i file -->
<link rel="stylesheet" href="https://TUO_DOMINIO/chat-widget.css">
<script type="module" src="https://TUO_DOMINIO/chat-widget.js"></script>
```

Lo script si occuperà automaticamente di creare il container `#helpdesk-widget-container` alla fine del `<body>` e di montarvi l'applicazione React.

> **Nota per il CSS**: Ricorda di adattare l'interfaccia (in `App.tsx` o `index.css`) in modo che l'app non occupi l'intero schermo del sito padre, ma appaia invece come un pannello flottante (es. applicando `position: fixed; bottom: 20px; right: 20px; z-index: 9999;` al contenitore principale).

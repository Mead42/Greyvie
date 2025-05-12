# Web UI

The **Web UI** is the React-based frontend for the DiabetesAI platform, built with Vite for fast HMR and minimal configuration. It provides users with a responsive dashboard to:

- View blood glucose (BG) trends over time
- Log meals by photo or manual entry
- Connect to fitness trackers and CGM devices
- Receive recommended meals and activities based on ML forecasts

This repo uses TypeScript, ESLint, and Prettier for code quality and consistency.

---

## 🚀 Features

- **Fast Refresh** via Vite and `@vitejs/plugin-react`
- **TypeScript** support out of the box
- **Tailwind CSS** for utility-first styling
- **Shadcn/UI** components for a consistent design system
- **Charting** with Recharts (or Chart.js) for timeline visualizations
- **Environment-based configuration** using `.env` files

---

## 🔧 Prerequisites

- **Node.js** v16+ (LTS)
- **npm** v8+ or **yarn** v1.22+

---

## 🏁 Getting Started

1. **Clone the monorepo**
   ```bash
   git clone https://github.com/your-org/GreyVie.git
   cd GreyVie/web-ui
   ```

2. **Install dependencies**
   ```bash
   npm install
   # or
   yarn install
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` to point at your local or staging API:
   ```env
   VITE_API_URL=http://localhost:4000
   VITE_GOOGLE_ANALYTICS_ID=G-XXXXXXX  # optional
   ```

4. **Run the dev server**
   ```bash
   npm run dev
   # or
   yarn dev
   ```
   Open http://localhost:3000 in your browser.

---

## ⚙️ Available Scripts

| Command         | Description                           |
| --------------- | ------------------------------------- |
| `dev`           | Start Vite dev server (HMR enabled)   |
| `build`         | Bundle for production (output: `dist`)|
| `preview`       | Preview production build locally      |
| `lint`          | Run ESLint over `src/`                |
| `format`        | Run Prettier on entire project       |
| `test`          | Run Vitest unit tests                 |

Execute via npm:
```bash
npm run dev
npm run build
npm run preview
npm run lint
npm run format
npm run test
```

---

## 🗂️ Project Structure

```
web-ui/
├── public/               # static assets and index.html
├── src/
│   ├── assets/           # images, fonts, icons
│   ├── components/       # reusable UI components
│   ├── pages/            # route-level pages (Dashboard, Settings, LogMeal)
│   ├── hooks/            # custom React hooks (useAuth, useFetch)
│   ├── services/         # API clients (Auth, Meals, BG, Activity)
│   ├── styles/           # Tailwind config, globals.css
│   ├── App.tsx           # root component with routing
│   └── main.tsx          # entry point, renders App
├── .env.example
├── package.json
├── tsconfig.json         # TypeScript configuration
├── vite.config.ts        # Vite configuration with React plugin
└── README.md             # this file
```

---

## 🧩 Vite & Plugins

This project uses:

- **@vitejs/plugin-react** for React Fast Refresh
- **Tailwind CSS** via PostCSS

Your `vite.config.ts` includes:
```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { port: 3000 }
})
```

---

## 🚨 ESLint & Prettier

Extend ESLint for type-aware rules. Install and configure:
```bash
npm install --save-dev eslint @typescript-eslint/parser @typescript-eslint/eslint-plugin eslint-plugin-react eslint-config-prettier prettier
```

Example `.eslintrc.js`:
```js
module.exports = {
  parser: '@typescript-eslint/parser',
  extends: [
    'eslint:recommended',
    'plugin:react/recommended',
    'plugin:@typescript-eslint/recommended',
    'prettier'
  ],
  parserOptions: { ecmaFeatures: { jsx: true } },
  settings: { react: { version: 'detect' } },
  rules: { /* your overrides */ }
}
```

For stricter, type-checked rules use:
```js
extends: [
  ...require('tseslint').configs.recommendedTypeChecked,
  /* ... other configs */
]
```

---

## 🔎 Testing

This template uses **Vitest** for unit tests.

- Write tests alongside components in `*.test.tsx` files.
- Run:

```bash
npm run test
# or
yarn test
```

- For coverage:

```bash
npm run test -- --coverage
```

---

## 🌐 Environmental Configuration

- **`.env`** loaded at build time with `import.meta.env.VITE_*`
- Sensitive values should be stored in your CI/CD pipeline secrets.

---

## 🚀 Production Deployment

1. **Build**:

   ```bash
   npm run build
   # or
   yarn build
   ```

2. **Host**:

   - **Static site**: upload `dist/` to S3 + CloudFront, Netlify, or Vercel.
   - **Container**: serve `dist/` via Nginx in a Docker container.

3. **Configure** your CI/CD (e.g., GitHub Actions) to run lint, tests, build, and deploy on `main` branch merges.

---

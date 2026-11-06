import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The board calls the FastAPI backend directly at VITE_API_URL (http://localhost:8000,
// set in .env). The backend allows this page's origin, http://localhost:5173, through CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true, // the backend's CORS list expects exactly this port
    open: true, // `npm run dev` opens the desk in the browser
  },
})

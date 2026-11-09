import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 出力は ../web/ 。FastAPI の StaticFiles がそこを配信するので、
// コンテナは1つのまま（フロント用の別ホスティングを持たない）。
export default defineConfig({
  plugins: [react()],
  build: { outDir: '../web', emptyOutDir: true },
  server: { proxy: { '/api': 'http://localhost:8077' } },
})

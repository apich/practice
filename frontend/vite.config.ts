import path from 'path';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import svgr from 'vite-plugin-svgr';

const BACKEND_URL = 'http://localhost:9000';

export default defineConfig({
	plugins: [react(), tailwindcss(), svgr()],
	server: {
		host: '0.0.0.0',
		proxy: {
			// Backend API paths — proxied to the FastAPI server.
			'/auth': BACKEND_URL,
			'/health': BACKEND_URL,
			'/api': BACKEND_URL,
			'/agent': BACKEND_URL,
			'/model': BACKEND_URL,
			'/tts-model': BACKEND_URL,
			'/channel': BACKEND_URL,
			'/credential': BACKEND_URL,
			'/knowledge_bases': BACKEND_URL,
			'/workspace': BACKEND_URL,
			'/hub': BACKEND_URL,
			'/sessions': BACKEND_URL,
			'/agents': BACKEND_URL,
			'/chat': BACKEND_URL,
			'/credentials': BACKEND_URL,
			'/schedule': BACKEND_URL,
			'/models': BACKEND_URL,
			'/publish': BACKEND_URL,
		},
	},
	resolve: {
		alias: {
			'@': path.resolve(__dirname, './src'),
			'next/navigation': path.resolve(__dirname, './src/lib/next-navigation-shim.ts'),
		},
	},
	optimizeDeps: {
		include: ['mime-types'],
	},
});

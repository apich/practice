/**
 * Polyfill for `crypto.randomUUID` — some older browsers (e.g. Safari < 15.4)
 * and Node < 19 do not expose it. We patch it once at app entry so every
 * downstream call site works without modification.
 */
if (typeof crypto !== 'undefined' && typeof crypto.randomUUID !== 'function') {
	(crypto as Crypto).randomUUID = (): string =>
		'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
			const r = (Math.random() * 16) | 0;
			const v = c === 'x' ? r : (r & 0x3) | 0x8;
			return v.toString(16);
		});
}

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import './index.css';
import './i18n';
import App from './App.tsx';
import { TooltipProvider } from '@/components/ui/tooltip.tsx';

createRoot(document.getElementById('root')!).render(
	<StrictMode>
		<TooltipProvider>
			<App />
		</TooltipProvider>
	</StrictMode>,
);

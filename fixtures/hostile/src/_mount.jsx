// Shared mount helper (not an entry: it starts with "_"). Pages report through window.__hostile.
import { createRoot } from 'react-dom/client';

export function mount(element) {
  createRoot(document.getElementById('root')).render(element);
  // After React's first commit; the runner waits for this before observing the page.
  requestAnimationFrame(() => requestAnimationFrame(() => window.__hostile.ready()));
}

export const done = detail => window.__hostile.done(detail);
export const progress = detail => window.__hostile.progress(detail);

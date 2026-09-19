import React from 'react';
import {createRoot} from 'react-dom/client';
import {CustomMessageComposer} from './components/CustomMessageComposer.jsx';
import {AutoPressRelease} from './components/AutoPressRelease.jsx';
import './composer.css';
const roots = new Map();
function mount() {
  document.querySelectorAll('[data-auto-press-release]').forEach(node => {
    if (roots.has(node)) return;
    const root = createRoot(node); roots.set(node, root);
    const onState = state => {
      const label = node.closest('.pack')?.querySelector('.pack__st');
      if (label) label.textContent = state.status === 'ready' ? state.label : state.status === 'blocked' ? 'Angaben fehlen' : state.status === 'failed' ? 'Erstellung unterbrochen' : state.status === 'queued' ? 'Im Hintergrund eingeplant' : state.stage === 'writing' ? `${state.words || 0} Wörter geschrieben` : state.stage === 'checking' ? 'Text geschrieben · Prüfung läuft' : 'Wird vorbereitet';
    };
    root.render(<AutoPressRelease clientId={Number(node.dataset.clientId)} angleId={Number(node.dataset.angleId)} onState={onState} />);
  });
  document.querySelectorAll('[data-custom-composer]').forEach(node => {
    if (roots.has(node)) return;
    const root = createRoot(node); roots.set(node, root);
    root.render(<CustomMessageComposer clientId={Number(node.dataset.clientId)} angleId={Number(node.dataset.angleId)} initialVersion={node.dataset.version} released={node.dataset.released === 'true'} />);
  });
}
mount();
document.addEventListener('htmx:afterSwap', mount);
document.addEventListener('htmx:beforeCleanupElement', event => {
  for (const [node, root] of roots) if (node === event.detail.elt || event.detail.elt.contains(node)) {root.unmount(); roots.delete(node);}
});

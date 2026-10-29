// CodeMirror 6: its own input handling over a contenteditable; the document is CodeMirror state, not the DOM.
import { EditorView, basicSetup } from 'codemirror';
import { EditorState } from '@codemirror/state';

const TARGET = 'const answer = 42';
const root = document.getElementById('root');
root.insertAdjacentHTML('beforebegin', '<p>Type <code>const answer = 42</code> in the editor</p>');
new EditorView({ parent: root, state: EditorState.create({ doc: '', extensions: [basicSetup,
  EditorView.contentAttributes.of({ 'aria-label': 'Code' }),
  EditorView.updateListener.of(update => { if (!update.docChanged) return;
    const text = update.state.doc.toString(); window.__hostile.progress({ text });
    if (text.includes(TARGET)) window.__hostile.done({ text }); })] }) });
requestAnimationFrame(() => window.__hostile.ready());

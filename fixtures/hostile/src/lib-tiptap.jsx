// TipTap (ProseMirror): text arrives through beforeinput/keydown handling; DOM edits are reconciled away.
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { mount, done, progress } from './_mount.jsx';

const TARGET = 'kitsune test';
function App() {
  const editor = useEditor({ extensions: [StarterKit], content: '<p></p>',
    editorProps: { attributes: { 'aria-label': 'Note', role: 'textbox' } },
    onUpdate: ({ editor }) => { const text = editor.getText(); progress({ text }); if (text.includes(TARGET)) done({ text }); } });
  return <div><p>Write "kitsune test" in the note</p><EditorContent editor={editor} /></div>;
}
mount(<App />);

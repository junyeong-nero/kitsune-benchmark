// React controlled input: only React's onChange (fed by real input events) updates state.
import { useState } from 'react';
import { mount, done, progress } from './_mount.jsx';

const TARGET = 'Ada Lovelace';
function App() {
  const [name, setName] = useState('');
  return (<form onSubmit={e => e.preventDefault()}>
    <label>Display name <input aria-label="Display name" value={name} onChange={e => {
      setName(e.target.value); progress({ value: e.target.value });
      if (e.target.value === TARGET) done({ value: e.target.value });
    }} /></label>
    <p>Saved name: {name || '(empty)'}</p>
  </form>);
}
mount(<App />);

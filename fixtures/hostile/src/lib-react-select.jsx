// react-select: a searchable combobox driven by mouse-down and keyboard handlers, not a native <select>.
import Select from 'react-select';
import { mount, done } from './_mount.jsx';

const options = ['Apple', 'Banana', 'Cherry', 'Mango', 'Orange', 'Peach'].map(v => ({ value: v.toLowerCase(), label: v }));
mount(<div style={{ width: 320 }}>
  <label id="fruit-label">Favorite fruit</label>
  <Select aria-labelledby="fruit-label" inputId="fruit" options={options} placeholder="Choose a fruit"
    onChange={option => option?.value === 'mango' && done({ value: option.value })} />
</div>);

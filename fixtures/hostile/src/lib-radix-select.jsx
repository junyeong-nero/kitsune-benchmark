// Radix Select: a custom listbox (pointerdown/pointerup selection, typeahead), not a native <select>.
import * as Select from '@radix-ui/react-select';
import { mount, done } from './_mount.jsx';

mount(<div>
  <span id="theme-label">Theme</span>
  <Select.Root onValueChange={v => v === 'dark' && done({ value: v })}>
    <Select.Trigger aria-labelledby="theme-label" aria-label="Theme"><Select.Value placeholder="Pick a theme" /></Select.Trigger>
    <Select.Portal>
      <Select.Content position="popper" style={{ background: '#fff', border: '1px solid #888' }}>
        <Select.Viewport>
          {['Light', 'Dark', 'System'].map(t => <Select.Item key={t} value={t.toLowerCase()}>
            <Select.ItemText>{t}</Select.ItemText></Select.Item>)}
        </Select.Viewport>
      </Select.Content>
    </Select.Portal>
  </Select.Root>
</div>);

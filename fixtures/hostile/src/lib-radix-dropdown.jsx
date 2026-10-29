// Radix DropdownMenu: the trigger opens on pointerdown (button 0, not ctrl) or keyboard, not on click.
import * as Menu from '@radix-ui/react-dropdown-menu';
import { mount, done } from './_mount.jsx';

mount(<Menu.Root>
  <Menu.Trigger>Options</Menu.Trigger>
  <Menu.Portal>
    <Menu.Content style={{ background: '#fff', border: '1px solid #888', padding: 4 }}>
      <Menu.Item onSelect={() => {}}>Duplicate</Menu.Item>
      <Menu.Item onSelect={() => done({ item: 'archive' })}>Archive</Menu.Item>
      <Menu.Item onSelect={() => {}}>Delete</Menu.Item>
    </Menu.Content>
  </Menu.Portal>
</Menu.Root>);

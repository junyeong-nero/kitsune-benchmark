// dnd-kit sortable: pointer sensor (5 px activation distance) and keyboard sensor (Space, arrows, Space).
import { useState } from 'react';
import { DndContext, PointerSensor, KeyboardSensor, closestCenter, useSensor, useSensors } from '@dnd-kit/core';
import { SortableContext, arrayMove, useSortable, verticalListSortingStrategy, sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { mount, done, progress } from './_mount.jsx';

function Item({ id }) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id });
  return <li ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition, padding: 8,
    margin: 4, border: '1px solid #999', listStyle: 'none', background: '#fafafa' }}>
    <button aria-label={`Drag ${id}`} {...attributes} {...listeners}>⠿</button> {id}</li>;
}
function App() {
  const [items, setItems] = useState(['Alpha', 'Bravo', 'Charlie', 'Delta']);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }));
  return <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={({ active, over }) => {
    if (!over || active.id === over.id) return;
    const next = arrayMove(items, items.indexOf(active.id), items.indexOf(over.id));
    setItems(next); progress({ order: next });
    if (next[0] === 'Delta') done({ order: next });
  }}>
    <p>Move Delta to the top</p>
    <SortableContext items={items} strategy={verticalListSortingStrategy}>
      <ul>{items.map(id => <Item key={id} id={id} />)}</ul>
    </SortableContext>
  </DndContext>;
}
mount(<App />);

// react-day-picker: a calendar grid of buttons with its own focus and keyboard model.
import { DayPicker } from 'react-day-picker';
import { mount, done } from './_mount.jsx';

mount(<div><p>Pick November 18, 2026</p>
  <DayPicker mode="single" defaultMonth={new Date(2026, 10, 1)}
    onSelect={day => day && day.getFullYear() === 2026 && day.getMonth() === 10 && day.getDate() === 18 && done({ day: 18 })} />
</div>);

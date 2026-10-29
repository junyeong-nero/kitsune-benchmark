// Radix Slider: pointer events with pointer capture on the track, arrow keys on the thumb.
import * as Slider from '@radix-ui/react-slider';
import { mount, done, progress } from './_mount.jsx';

const style = { root: { position: 'relative', display: 'flex', alignItems: 'center', width: 300, height: 24 },
  track: { position: 'relative', flexGrow: 1, height: 4, background: '#ccc' },
  range: { position: 'absolute', height: '100%', background: '#36c' },
  thumb: { display: 'block', width: 18, height: 18, borderRadius: 9, background: '#36c' } };
mount(<div>
  <p>Volume (set it to 80)</p>
  <Slider.Root style={style.root} defaultValue={[50]} max={100} step={1}
    onValueChange={([v]) => { progress({ value: v }); if (v === 80) done({ value: v }); }}>
    <Slider.Track style={style.track}><Slider.Range style={style.range} /></Slider.Track>
    <Slider.Thumb style={style.thumb} aria-label="Volume" />
  </Slider.Root>
</div>);

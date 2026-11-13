// Bundles each src/<id>.jsx into artifacts/hostile/bundle/<id>.js (gitignored). No network at run time.
import { build } from 'esbuild';
import { readdirSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const out = path.resolve(here, '../../artifacts/hostile/bundle');
mkdirSync(out, { recursive: true });
const entries = readdirSync(path.join(here, 'src')).filter(f => f.endsWith('.jsx') && !f.startsWith('_')).map(f => path.join(here, 'src', f));
await build({
  entryPoints: entries, outdir: out, bundle: true, minify: true, format: 'iife', target: 'firefox115',
  jsx: 'automatic', define: { 'process.env.NODE_ENV': '"production"' }, logLevel: 'warning', legalComments: 'none',
});
console.log(`built ${entries.length} bundles into ${out}`);

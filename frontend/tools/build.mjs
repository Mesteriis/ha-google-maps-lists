import {build} from 'esbuild';import {mkdir,copyFile,writeFile,readFile} from 'node:fs/promises';import path from 'node:path';import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const out=path.resolve(root,'../custom_components/google_maps_lists/frontend');await mkdir(out,{recursive:true});
await build({entryPoints:[path.join(root,'src/card.js')],outfile:path.join(out,'belovodie-places-card.js'),bundle:true,minify:true,format:'esm',target:'es2022',loader:{'.css':'text'},legalComments:'eof'});
await build({entryPoints:[path.join(root,'node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs')],outfile:path.join(out,'maplibre-worker.mjs'),bundle:true,minify:true,format:'esm',target:'es2022',legalComments:'eof'});
const licenses=await Promise.all(['lit','maplibre-gl','esbuild'].map(async name=>{const pkg=path.join(root,'node_modules',name);const file=name==='esbuild'?'LICENSE.md':name==='maplibre-gl'?'LICENSE.txt':'LICENSE';return `${name}\n${await readFile(path.join(pkg,file),'utf8')}\n`;}));
await writeFile(path.join(out,'LICENSES.txt'),licenses.join('\n'));
console.log('Built belovodie-places-card locally (JS, worker, licenses)');

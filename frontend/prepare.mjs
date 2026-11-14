import {cp,mkdir} from 'node:fs/promises';
await mkdir('public/pdfjs',{recursive:true});
for (const name of ['standard_fonts','cmaps','wasm']) await cp(`node_modules/pdfjs-dist/${name}`,`public/pdfjs/${name}`,{recursive:true});

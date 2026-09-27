import { deflateSync } from '../scripts/terraria-player-map-renderer/node_modules/fflate/esm/browser.js';
import { FileReader } from '../scripts/terraria-player-map-renderer/node_modules/terraria-world-file/dist/index.mjs';
import { createMapPreview, buildMapFromParsedWorld } from '../scripts/terraria-player-map-renderer/examples/map-from-parsed-world.mjs';

async function readAllStdin() {
  return await new Promise((resolve, reject) => {
    const chunks = [];
    process.stdin.on('data', (chunk) => {
      chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
    });
    process.stdin.on('end', () => resolve(Buffer.concat(chunks)));
    process.stdin.on('error', reject);
    process.stdin.resume();
  });
}

async function main() {
  const input = await readAllStdin();
  if (!input || input.length === 0) {
    throw new Error('No world data received on stdin');
  }

  const file = Buffer.from(input);
  const fileBuffer = file.buffer.slice(file.byteOffset, file.byteOffset + file.byteLength);
  const parser = await new FileReader().loadBuffer(fileBuffer);
  const parsedFile = parser.parse({ sections: ['fileFormatHeader'] });
  const version = parsedFile.fileFormatHeader.version;
  const parsedHeader = parser.parse({
    sections: ['header'],
    ignorePointers: version >= 323,
  });
  const parsedTiles = parser.parse({ sections: ['worldTiles'] });
  const parsedWorld = { ...parsedFile, ...parsedHeader, ...parsedTiles };
  const preview = createMapPreview(parsedWorld);

  const result = await buildMapFromParsedWorld(parsedWorld, {
    compress: deflateSync,
  });

  process.stdout.write(JSON.stringify({
    filename: result.fileName,
    data: Buffer.from(result.bytes).toString('base64'),
    preview: {
      width: preview.width,
      height: preview.height,
      pixels: Buffer.from(preview.pixels).toString('base64'),
    },
  }));
}

main().catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`${message}\n`);
  process.exit(1);
});

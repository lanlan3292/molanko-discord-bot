#!/usr/bin/env node
/**
 * Badge renderer for molanko-discord-bot.
 *
 * Reads a Badgeworks config JSON from argv[2] and writes a JSON envelope to
 * stdout:
 *   { "png": "<base64>", "svg": "<svg markup>", "width": n, "height": n }
 *
 * Any library log output must go to stderr so stdout stays a clean payload.
 */

const _err = console.error.bind(console);
console.log = (...args) => _err(...args);
console.info = (...args) => _err(...args);

import { generateBadge, svgToPng } from '../badgeworks/src/index.js';

const raw = process.argv[2];
if (!raw) {
  _err('Missing config JSON');
  process.exit(1);
}

let cfg;
try {
  cfg = JSON.parse(raw);
} catch (e) {
  _err('Invalid config JSON: ' + e.message);
  process.exit(1);
}

function readStdin() {
  return new Promise((resolve, reject) => {
    const chunks = [];
    process.stdin.on('data', (c) => chunks.push(c));
    process.stdin.on('end', () => resolve(Buffer.concat(chunks)));
    process.stdin.on('error', reject);
    process.stdin.resume();
  });
}

(async () => {
  // Upload mode: image bytes arrive on stdin (argv has a size limit, so we
  // can't embed a large base64 data URL in the config JSON).
  if (cfg.iconMode === 'upload' && !cfg.imageDataUrl) {
    const buf = await readStdin();
    const mime = cfg.imageMimeType || 'image/png';
    cfg.imageDataUrl = `data:${mime};base64,${buf.toString('base64')}`;
    delete cfg.imageMimeType;
  }

  const svg = await generateBadge(cfg);

  // SVG mode still returns the raw markup for parity with other scripts.
  if (process.argv[3] === 'svg') {
    process.stdout.write(svg);
    return;
  }

  const dim = svg.match(/width="(\d+)"\s+height="(\d+)"/);
  const png = await svgToPng(svg);

  const result = {
    png: Buffer.from(png).toString('base64'),
    svg,
    width: dim ? parseInt(dim[1], 10) : null,
    height: dim ? parseInt(dim[2], 10) : null
  };
  process.stdout.write(JSON.stringify(result));
})().catch((e) => {
  _err((e && e.stack) || String(e));
  process.exit(1);
});
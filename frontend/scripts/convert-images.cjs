const fs = require('fs');
const path = require('path');
const sharp = require('sharp');

function walk(dir, ext = '.png', files = []) {
  const list = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of list) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full, ext, files);
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith(ext)) {
      files.push(full);
    }
  }
  return files;
}

async function convert(filePath) {
  try {
    const out = filePath.replace(/\.png$/i, '.webp');
    await sharp(filePath).webp({ quality: 80 }).toFile(out);
    console.log(`converted: ${filePath} -> ${out}`);
  } catch (err) {
    console.error('failed to convert', filePath, err.message);
  }
}

(async () => {
  const repoRoot = path.resolve(__dirname, '..');

  // Convert root-level image.png if present
  const rootPng = path.join(repoRoot, 'image.png');
  if (fs.existsSync(rootPng)) {
    await convert(rootPng);
  }

  // Convert pngs under src/ and public/ (common asset locations)
  const candidates = [];
  const srcDir = path.join(repoRoot, 'src');
  const publicDir = path.join(repoRoot, 'public');
  if (fs.existsSync(srcDir)) candidates.push(...walk(srcDir));
  if (fs.existsSync(publicDir)) candidates.push(...walk(publicDir));

  for (const f of candidates) {
    await convert(f);
  }

  console.log('image conversion finished');
})();
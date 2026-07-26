const fs = require('node:fs');
const crypto = require('node:crypto');
const path = require('node:path');

function sha256File(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

function copyIfChecksumDiffers(source, target) {
  if (fs.existsSync(target) && sha256File(source) === sha256File(target)) {
    return false;
  }
  fs.copyFileSync(source, target);
  return true;
}

function copyTreeIfMissing(sourceDir, targetDir) {
  if (!fs.existsSync(sourceDir) || fs.existsSync(targetDir)) {
    return false;
  }
  fs.mkdirSync(path.dirname(targetDir), { recursive: true });
  fs.cpSync(sourceDir, targetDir, {
    recursive: true,
    filter: (source) => !source.includes('__pycache__') && !source.endsWith('.pyc'),
  });
  return true;
}

function syncTreeByChecksum(sourceDir, targetDir) {
  if (!fs.existsSync(sourceDir)) return 0;
  let copied = 0;
  for (const entry of fs.readdirSync(sourceDir, { withFileTypes: true })) {
    if (entry.name === '__pycache__' || entry.name.endsWith('.pyc')) continue;
    const source = path.join(sourceDir, entry.name);
    const target = path.join(targetDir, entry.name);
    if (entry.isDirectory()) {
      copied += syncTreeByChecksum(source, target);
      continue;
    }
    fs.mkdirSync(targetDir, { recursive: true });
    copied += copyIfChecksumDiffers(source, target) ? 1 : 0;
  }
  return copied;
}

module.exports = { copyIfChecksumDiffers, copyTreeIfMissing, sha256File, syncTreeByChecksum };

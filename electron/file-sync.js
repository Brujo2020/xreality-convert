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

module.exports = { copyIfChecksumDiffers, copyTreeIfMissing, sha256File };

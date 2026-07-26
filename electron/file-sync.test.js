const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { copyIfChecksumDiffers, copyTreeIfMissing, sha256File, syncTreeByChecksum } = require('./file-sync');

test('copyIfChecksumDiffers repairs only missing or changed files', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ois-file-sync-'));
  try {
    const source = path.join(dir, 'source.py');
    const target = path.join(dir, 'target.py');
    fs.writeFileSync(source, 'one');

    assert.equal(copyIfChecksumDiffers(source, target), true);
    const firstHash = sha256File(target);
    assert.equal(copyIfChecksumDiffers(source, target), false);

    fs.writeFileSync(source, 'two');
    assert.equal(copyIfChecksumDiffers(source, target), true);
    assert.notEqual(sha256File(target), firstHash);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('copyTreeIfMissing copies runtime trees without bytecode caches', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ois-file-tree-'));
  try {
    const source = path.join(dir, 'source');
    const target = path.join(dir, 'target');
    fs.mkdirSync(path.join(source, 'module', '__pycache__'), { recursive: true });
    fs.writeFileSync(path.join(source, 'module', 'texture.py'), 'paint');
    fs.writeFileSync(path.join(source, 'module', '__pycache__', 'texture.pyc'), 'cache');

    assert.equal(copyTreeIfMissing(source, target), true);
    assert.equal(fs.readFileSync(path.join(target, 'module', 'texture.py'), 'utf8'), 'paint');
    assert.equal(fs.existsSync(path.join(target, 'module', '__pycache__')), false);
    assert.equal(copyTreeIfMissing(source, target), false);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('syncTreeByChecksum updates bundled runtime files without deleting upstream files', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ois-file-tree-sync-'));
  try {
    const source = path.join(dir, 'source');
    const target = path.join(dir, 'target');
    fs.mkdirSync(path.join(source, 'module'), { recursive: true });
    fs.mkdirSync(path.join(target, 'module'), { recursive: true });
    fs.writeFileSync(path.join(source, 'module', 'texture.py'), 'new');
    fs.writeFileSync(path.join(target, 'module', 'texture.py'), 'old');
    fs.writeFileSync(path.join(target, 'upstream.py'), 'keep');

    assert.equal(syncTreeByChecksum(source, target), 1);
    assert.equal(fs.readFileSync(path.join(target, 'module', 'texture.py'), 'utf8'), 'new');
    assert.equal(fs.readFileSync(path.join(target, 'upstream.py'), 'utf8'), 'keep');
    assert.equal(syncTreeByChecksum(source, target), 0);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

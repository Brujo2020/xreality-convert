const { app, BrowserWindow } = require('electron');
const path = require('node:path');
const fs = require('node:fs/promises');

const root = path.resolve(__dirname, '..');
const outputDir = process.env.XREALITY_SMOKE_OUTPUT || path.join(root, 'ui-smoke-output');
const smokeState = process.env.XREALITY_SMOKE_STATE || 'ready';
const width = Number(process.env.XREALITY_SMOKE_WIDTH || 1280);
const height = Number(process.env.XREALITY_SMOKE_HEIGHT || 800);
const pause = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

app.whenReady().then(async () => {
  await fs.mkdir(outputDir, { recursive: true });
  const window = new BrowserWindow({
    width,
    height,
    show: false,
    backgroundColor: '#020b1c',
    webPreferences: {
      preload: path.join(__dirname, 'ui-smoke-preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });
  const consoleProblems = [];
  let rendererGone = null;
  window.webContents.on('console-message', (_event, level, message) => {
    if (level >= 2) consoleProblems.push(message);
  });
  window.webContents.on('render-process-gone', (_event, details) => {
    rendererGone = details;
    consoleProblems.push(`Renderer finalizado: ${details.reason} (${details.exitCode})`);
  });
  await window.loadFile(path.join(root, 'dist', 'index.html'));
  await pause(900);
  const quickProfileCheck = await window.webContents.executeJavaScript(`(() => {
    const button = document.querySelector('[data-profile-id="lowpoly"]');
    if (!button) return { exists: false, selected: false };
    button.click();
    return { exists: true };
  })()`);
  await pause(100);
  quickProfileCheck.selected = await window.webContents.executeJavaScript(`document.querySelector('[data-profile-id="lowpoly"]')?.getAttribute('aria-pressed') === 'true'`);
  if (!quickProfileCheck.exists || !quickProfileCheck.selected) {
    consoleProblems.push('El selector rápido Low Poly no se pudo activar.');
  }
  await fs.writeFile(path.join(outputDir, `${smokeState}-${width}x${height}.png`), (await window.webContents.capturePage()).toPNG());

  let resultActionCheck = null;
  if (process.env.XREALITY_SMOKE_GLB || process.env.XREALITY_SMOKE_RESULT_IMAGE) {
    await window.webContents.executeJavaScript(`
      [...document.querySelectorAll('button')].find((button) => button.textContent.includes('Historial'))?.click();
    `);
    await pause(250);
    await window.webContents.executeJavaScript(`
      document.querySelector('button[title="Referencia de control visual"]')?.click();
    `);
    await pause(1600);
    if (!rendererGone && !window.webContents.isDestroyed()) {
      try {
        resultActionCheck = await window.webContents.executeJavaScript(`(() => ({
          openUsd: [...document.querySelectorAll('button')].some((button) => button.textContent.includes('Exportar USDZ')),
          stl: [...document.querySelectorAll('button')].some((button) => button.textContent.includes('Exportar STL')),
        }))()`);
      } catch (error) {
        consoleProblems.push(`No se pudo inspeccionar el resultado GLB: ${error.message}`);
      }
    }
    if (process.env.XREALITY_SMOKE_GLB && (!resultActionCheck?.openUsd || !resultActionCheck?.stl)) {
      consoleProblems.push('Faltan acciones GLB de exportación STL/OpenUSD.');
    }
    if (!rendererGone && !window.webContents.isDestroyed()) {
      await fs.writeFile(path.join(outputDir, `result-${width}x${height}.png`), (await window.webContents.capturePage()).toPNG());
    }
  }

  const result = {
    outputDir,
    smokeState,
    consoleProblems,
    quickProfileCheck,
    resultActionCheck,
    rendererGone,
    dimensions: rendererGone || window.webContents.isDestroyed()
      ? null
      : await window.webContents.executeJavaScript(`({ width: innerWidth, height: innerHeight, bodyScrollWidth: document.body.scrollWidth, bodyClientWidth: document.body.clientWidth })`),
  };
  process.stdout.write(`${JSON.stringify(result)}\n`);
  if (!window.isDestroyed()) window.destroy();
  if (consoleProblems.length) app.exit(1);
  else app.quit();
});

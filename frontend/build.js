const fs = require('fs');
const path = require('path');

const root = __dirname;
const dist = path.join(root, 'dist');

function copyDir(source, target) {
  fs.mkdirSync(target, { recursive: true });
  for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
    const sourcePath = path.join(source, entry.name);
    const targetPath = path.join(target, entry.name);
    if (entry.isDirectory()) {
      copyDir(sourcePath, targetPath);
    } else {
      fs.copyFileSync(sourcePath, targetPath);
    }
  }
}

fs.rmSync(dist, { recursive: true, force: true });
fs.mkdirSync(dist, { recursive: true });

copyDir(path.join(root, 'atm'), path.join(dist, 'atm'));
copyDir(path.join(root, 'mobile'), path.join(dist, 'mobile'));
copyDir(path.join(root, 'register'), path.join(dist, 'register'));

const apiBase = (
  process.env.VITE_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.API_BASE_URL ||
  ''
).replace(/\/$/, '');

fs.writeFileSync(
  path.join(dist, 'config.js'),
  `window.ATM_AUTH_API_BASE = ${JSON.stringify(apiBase)};\n`,
  'utf8'
);

fs.writeFileSync(
  path.join(dist, 'index.html'),
  '<!doctype html><meta http-equiv="refresh" content="0; url=/atm/"><script>location.replace("/atm/");</script>',
  'utf8'
);

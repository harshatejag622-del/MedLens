const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

console.log('=== Starting MedLens Production Build ===');

let rootDir = __dirname;
if (!fs.existsSync(path.join(rootDir, 'frontend'))) {
  if (fs.existsSync(path.join(rootDir, '..', 'frontend'))) {
    rootDir = path.join(rootDir, '..');
  }
}

const frontendDir = path.join(rootDir, 'frontend');
console.log('Frontend directory:', frontendDir);

console.log('1. Installing frontend dependencies...');
execSync('npm install', { cwd: frontendDir, stdio: 'inherit' });

console.log('2. Building Vite production bundle...');
execSync('npm run build', { cwd: frontendDir, stdio: 'inherit' });

const srcDist = path.join(frontendDir, 'dist');
const targets = [
  path.join(rootDir, 'dist'),
  path.join(rootDir, 'frontend', 'dist'),
  path.join(rootDir, 'backend', 'dist')
];

console.log('3. Distributing build artifacts to all paths...');
for (const target of targets) {
  try {
    if (target !== srcDist) {
      fs.mkdirSync(target, { recursive: true });
      fs.cpSync(srcDist, target, { recursive: true });
    }
    console.log('   Synced to:', target);
  } catch (e) {
    console.warn('   Warning syncing to:', target, e.message);
  }
}

console.log('=== MedLens Production Build Succeeded ===');

#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');

const SKILL_NAME = 'seedance-forge';
const SKIP = new Set(['.git', 'node_modules', 'package.json', 'install.js', '.npmignore']);

function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    if (SKIP.has(entry.name)) continue;
    const s = path.join(src, entry.name);
    const d = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDir(s, d);
    } else {
      fs.copyFileSync(s, d);
    }
  }
}

const targets = [
  { label: 'Claude Code', dest: path.join(os.homedir(), '.claude', 'skills', SKILL_NAME) },
  { label: 'Codex CLI',   dest: path.join(os.homedir(), '.codex',  'skills', SKILL_NAME) },
];

let installed = 0;

for (const { label, dest } of targets) {
  const base = path.dirname(dest);
  if (!fs.existsSync(base)) {
    console.log(`  skip ${label} (${base} not found)`);
    continue;
  }
  try {
    copyDir(__dirname, dest);
    console.log(`  ✓ ${label} → ${dest}`);
    installed++;
  } catch (err) {
    console.warn(`  ✗ ${label}: ${err.message}`);
  }
}

if (installed === 0) {
  console.error('\nNo skill host found. Install Claude Code or Codex CLI first.');
  process.exit(1);
}

console.log(`\nSeedance Forge installed (${installed} target${installed > 1 ? 's' : ''}).`);
console.log('Restart Claude Code then type:  /seedance-forge');

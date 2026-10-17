import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { prepare } from './prepare-docker-node.mjs';

test('only removes root developer tools; keeps workspace pins and overrides', () => {
  const root = mkdtempSync(join(tmpdir(), 'scanner-node-build-'));
  try {
    const original = readFileSync(new URL('../../pnpm-lock.yaml', import.meta.url), 'utf8');
    const manifest = JSON.parse(readFileSync(new URL('../../package.json', import.meta.url), 'utf8'));
    writeFileSync(join(root, 'package.json'), JSON.stringify(manifest));
    writeFileSync(join(root, 'pnpm-lock.yaml'), original);
    prepare(root);
    const prepared = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'));
    const lock = readFileSync(join(root, 'pnpm-lock.yaml'), 'utf8');
    assert.equal(prepared.devDependencies, undefined);
    assert.equal(prepared.scripts, undefined);
    assert.deepEqual(prepared.pnpm, manifest.pnpm);
    assert.equal(prepared.packageManager, manifest.packageManager);
    assert.ok(lock.includes('\n  .: {}\n'));
    const workspaceStart = '\n  apps/browser-extension:\n';
    assert.equal(lock.slice(lock.indexOf(workspaceStart)), original.slice(original.indexOf(workspaceStart)));
  } finally { rmSync(root, { recursive: true }); }
});

test('fails closed on an unexpected lock layout without editing the manifest', () => {
  const root = mkdtempSync(join(tmpdir(), 'scanner-node-build-'));
  try {
    writeFileSync(join(root, 'package.json'), '{"name":"unchanged"}');
    writeFileSync(join(root, 'pnpm-lock.yaml'), "lockfileVersion: '8.0'\n");
    assert.throws(() => prepare(root), /Unsupported/);
    assert.equal(readFileSync(join(root, 'package.json'), 'utf8'), '{"name":"unchanged"}');
  } finally { rmSync(root, { recursive: true }); }
});

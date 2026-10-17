// Run only inside the disposable Docker build context. Keep the pinned workspace
// graph and overrides, but do not install root-only developer tools (Supabase CLI).
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export function prepare(root) {
  const manifestPath = resolve(root, 'package.json');
  const lockPath = resolve(root, 'pnpm-lock.yaml');
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  const lock = readFileSync(lockPath, 'utf8');
  const start = lock.indexOf('\n  .:\n', lock.indexOf('\nimporters:\n'));
  if (start < 0 || !lock.startsWith("lockfileVersion: '9.0'\n")) {
    throw new Error('Unsupported pnpm lockfile layout: refusing to change dependency resolution.');
  }
  const remaining = lock.slice(start + '\n  .:\n'.length);
  const next = remaining.search(/\n  [^\s][^\n]*:\n/);
  if (next < 0) throw new Error('Expected a workspace importer after the root importer.');
  const end = start + '\n  .:\n'.length + next;
  for (const field of ['dependencies', 'devDependencies', 'optionalDependencies', 'scripts']) delete manifest[field];
  // Only the root importer changes. Workspace importers, snapshots and overrides
  // stay byte-for-byte pinned, so --frozen-lockfile continues to validate them.
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
  writeFileSync(lockPath, lock.slice(0, start) + '\n  .: {}\n' + lock.slice(end));
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  prepare(process.cwd());
}

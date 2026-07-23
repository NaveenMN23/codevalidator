// Convention-based file locking — no backend `lockedFiles` metadata yet (see
// PLATFORM_UI_RESTYLE_PLAN.md Part 3). Shared between Workspace.tsx (editor readOnly + tab
// badge) and FileExplorer.tsx (tree row badge) so the rule lives in exactly one place.
const LOCKED_EXACT = new Set(['pom.xml', 'package.json', 'README.md']);

export function isLockedPath(path: string): boolean {
  if (path.startsWith('tests/')) return true;
  return LOCKED_EXACT.has(path);
}

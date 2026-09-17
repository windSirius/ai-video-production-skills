#!/usr/bin/env python3
"""Read-only audit of a reviewed storage-root and compatibility-link manifest.

No directory traversal through media links, file hydration, migration or cleanup.
The host-specific manifest is local data and must not be committed to a public repo.
"""
import argparse
import fnmatch
import json
import os
from pathlib import Path

DEFAULT_MANIFEST = Path.home()/'Documents/视频工作区/00_管理/storage_roots.json'


def audit(manifest):
    config = json.loads(Path(manifest).read_text(encoding='utf-8'))
    if config.get('schema') != 'video_storage_roots_v1':
        raise ValueError('unsupported storage-root manifest')
    root = Path(config['workspace_root']).expanduser().resolve()
    errors = []
    if not root.is_dir():
        errors.append(f'workspace missing: {root}')
    if {'Mobile Documents', 'CloudStorage'} & set(root.parts):
        errors.append('local workspace is inside iCloud/File Provider')
    roots = []
    for key in ('media_root', 'cache_root'):
        path = Path(config[key]).expanduser().resolve()
        roots.append(path)
        if path == root or not path.is_relative_to(root) or not path.is_dir():
            errors.append(f'{key} must be an existing directory inside the workspace: {path}')
    if roots[0].is_relative_to(roots[1]) or roots[1].is_relative_to(roots[0]):
        errors.append('media and cache roots overlap')
    aliases = config.get('legacy_aliases', [])
    alias_paths = set()
    for row in aliases:
        path = Path(row['source']).expanduser().absolute()
        target = Path(row['target']).expanduser().resolve()
        alias_paths.add(path)
        if not path.is_symlink() or not path.exists() or path.resolve() != target:
            errors.append(f'legacy alias missing, replaced, or misdirected: {path}')
        if not target.is_relative_to(root):
            errors.append(f'legacy target outside workspace: {target}')
    for watch in config.get('watch_roots', []):
        parent = Path(watch['path']).expanduser()
        if not parent.is_dir():
            errors.append(f'watch root missing: {parent}')
            continue
        for path in parent.iterdir():
            if any(fnmatch.fnmatchcase(path.name, pattern) for pattern in watch['patterns']):
                if path.absolute() not in alias_paths:
                    errors.append(f'new scattered work path: {path}')
    allowed={str(Path(p).absolute()) for p in config.get('compatibility_allowlist', [])}
    for directory in config.get('compatibility_roots', []):
        directory=Path(directory).expanduser()
        if not directory.is_dir():
            errors.append(f'compatibility directory missing: {directory}')
            continue
        for folder,dirs,files in os.walk(directory,followlinks=False):
            for name in dirs+files:
                path=Path(folder)/name
                if name!='.DS_Store' and str(path.absolute()) not in allowed:
                    errors.append(f'new content in legacy-only compatibility directory: {path}')
            dirs[:]=[d for d in dirs if not (Path(folder)/d).is_symlink()]
    return {'status': 'FAIL' if errors else 'PASS', 'workspace_root': str(root),
            'legacy_alias_count': len(aliases), 'errors': errors,
            'media_hash_audit_performed': False, 'files_modified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    try:
        result = audit(args.manifest)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result['status'] == 'PASS' else 1
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(json.dumps({'status': 'FAIL', 'error': str(exc)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

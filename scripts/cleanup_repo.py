from __future__ import annotations

import argparse
import shutil
from pathlib import Path

SAFE_DIRS = [
    '__pycache__',
    '.pytest_cache',
    'pytest-cache-files-*',
    'tmp_structure_test',
    'output_pdfs',
    'backend/.pytest_cache',
    'backend/.tmp-test-docx-normalizer',
    'backend/output_pdfs',
    'backend/temp_uploads',
    'backend/test_output',
    'frontend/dist',
    'scripts/__pycache__',
    '.paddlex_tmp',
    '.paddlex_runtime_tmp',
    'htmlcov',
]

SAFE_FILE_GLOBS = [
    '*.log',
    '.coverage',
    '.coverage.*',
    'tmp_*',
    'backend/*.log',
    'backend/*.pyc',
    'tmp_page*.png',
    'tmp_page_*.png',
]

AGGRESSIVE_DIRS = [
    '.cache',
    '.paddle_env',
    '.paddlex',
    '.paddle_models',
    '.paddle_inference',
    'backend/venv',
    'frontend/node_modules',
]

EXTRA_LEGACY_TARGETS = [
    'AppData',
    'Microsoft',
    'pip',
    'backend/pip',
    'temp_ppstructure_download.py',
    'dev_output.log',
    'frontend_dev.log',
    'npm_install.log',
    'start_all.log',
    'start_dev.log',
]


def collect_targets(repo_root: Path, aggressive: bool) -> list[Path]:
    targets: set[Path] = set()

    def add_match(pattern: str) -> None:
        for match in repo_root.glob(pattern):
            if match.exists() and match != repo_root / '.git':
                targets.add(match)

    for pattern in SAFE_DIRS:
        add_match(pattern)
    for pattern in SAFE_FILE_GLOBS:
        add_match(pattern)
    for pattern in EXTRA_LEGACY_TARGETS:
        add_match(pattern)

    if aggressive:
        for pattern in AGGRESSIVE_DIRS:
            add_match(pattern)

    filtered: list[Path] = []
    for path in sorted(targets, key=lambda p: (len(p.parts), str(p))):
        if any(parent in targets for parent in path.parents if parent != repo_root):
            continue
        filtered.append(path)
    return filtered


def remove_path(path: Path, dry_run: bool) -> tuple[bool, str]:
    if dry_run:
        return True, f'[DRY] {path}'

    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
        return True, f'[DEL] {path}'
    except Exception as exc:
        return False, f'[ERR] {path} :: {exc}'


def main() -> int:
    parser = argparse.ArgumentParser(description='Clean generated and junk files from this repository.')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be removed without deleting anything.')
    parser.add_argument('--aggressive', action='store_true', help='Also remove environments, node_modules, and Paddle caches.')
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    targets = collect_targets(repo_root, aggressive=args.aggressive)

    print(f'Repo root: {repo_root}')
    print(f'Dry run : {args.dry_run}')
    print(f'Aggressive: {args.aggressive}')
    print(f'Matched: {len(targets)}')

    deleted = 0
    failed = 0
    for path in targets:
        ok, message = remove_path(path, dry_run=args.dry_run)
        print(message)
        if ok:
            deleted += 1
        else:
            failed += 1

    print('\nSummary')
    print('-------')
    print(f'Processed: {len(targets)}')
    print(f'Success : {deleted}')
    print(f'Failed  : {failed}')

    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())

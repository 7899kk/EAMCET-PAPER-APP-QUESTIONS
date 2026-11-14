"""Create corresponding source without generated files, secrets or PDFs."""
import sys
import zipfile
from pathlib import Path

ROOT_FILES = {'Dockerfile', '.dockerignore', '.gitignore', 'render.yaml', 'serve.py',
              'start.sh', 'preview.py', 'package.json', 'README.md', 'LICENSE',
              'NOTICE', 'requirements.txt', 'requirements.lock.txt', 'requirements-dev.txt', 'requirements-browser.txt'}
SOURCE_DIRS = {'backend', 'docs', 'scripts', 'THIRD_PARTY', 'research', 'tests', 'frontend'}
EXCLUDED = {'node_modules', '__pycache__', 'dist', 'public', 'artifacts', '.pytest_cache'}

def package(root, destination):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob('*')):
            relative = path.relative_to(root)
            if not path.is_file() or path.is_symlink() or path == destination:
                continue
            if any(p in EXCLUDED or p.startswith('.') for p in relative.parts):
                if len(relative.parts) != 1 or relative.name not in ROOT_FILES:
                    continue
            if relative.parts[0] not in SOURCE_DIRS and str(relative) not in ROOT_FILES:
                continue
            if path.suffix in ('.log', '.pyc', '.pdf', '.zip') or path.name.startswith('.env'):
                continue
            archive.write(path, Path('pdf-studio') / relative)

if __name__ == '__main__':
    package(sys.argv[1], sys.argv[2])

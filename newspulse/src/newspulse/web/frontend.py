"""Resolve Vite's built entry; the Python-only checkout keeps a working Desk."""
import json
from pathlib import Path

_WEB = Path(__file__).resolve().parent
BUILD_DIR = _WEB / 'static' / 'react'


def page_assets(page: str) -> dict | None:
    try:
        manifest = json.loads((BUILD_DIR / '.vite' / 'manifest.json').read_text())
        entry = manifest[f'src/{page}.jsx']
        imports = []
        pending = list(entry.get('imports', []))
        while pending:
            name = pending.pop()
            if name in imports:
                continue
            imports.append(name)
            pending.extend(manifest[name].get('imports', []))
        css = list(dict.fromkeys([*entry.get('css', []),
            *(path for name in imports for path in manifest[name].get('css', []))]))
        paths = [entry['file'], *css, *(manifest[name]['file'] for name in imports)]
        if not all((BUILD_DIR / path).is_file() for path in paths):
            return None
        return {'script': '/static/react/' + entry['file'],
                'css': ['/static/react/' + path for path in css]}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def desk_translations(translate) -> dict[str, str]:
    labels = json.loads((_WEB / 'desk_labels.json').read_text())
    return {label: translate(label) for label in labels}


def desk_assets() -> dict | None:
    return page_assets("desk")

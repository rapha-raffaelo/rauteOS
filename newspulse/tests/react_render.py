"""Render real React components when a route test inspects visible HTML.

TestClient cannot execute JavaScript. This adapter runs React's static renderer
on the actual JSON boot payload, never the retired Jinja page templates. Tests
for the raw response/JSON contract call response.text/json directly instead.
"""
import functools
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

_FRONTEND = Path(__file__).resolve().parents[2] / 'frontend'

@functools.lru_cache(maxsize=1)
def _build():
    node = shutil.which('node')
    if not node:
        candidates = sorted((Path.home()/'.nvm/versions/node').glob('*/bin/node'))
        node = str(candidates[-1]) if candidates else None
    if not node:
        raise RuntimeError('Node is required for React UI regression tests')
    env = dict(os.environ, PATH=str(Path(node).parent)+os.pathsep+os.environ['PATH'])
    build = subprocess.run([node, 'node_modules/vite/bin/vite.js', 'build', '--ssr',
                            'src/platform/render-test.jsx', '--outDir', '.test-render'],
                           cwd=_FRONTEND, env=env, text=True, capture_output=True)
    if build.returncode:
        raise RuntimeError('React test build failed. Use Node 22.22.3 and npm ci.\n'
                           + build.stdout + build.stderr)
    return node, env


def rendered(response):
    body = response.text
    if not isinstance(body, str):
        return body
    def payload(name):
        match = re.search(r'<script id="'+name+r'" type="application/json">(.*?)</script>',body,re.S)
        return json.loads(match[1]) if match else None
    shell = payload('react-shell-data')
    if not shell:
        return body
    page = re.search(r'id="react-platform" data-page="([^"]+)"',body)
    data = dict(shell=shell, tabs=payload('react-tabs-data'), data=payload('react-page-data'), page=page[1] if page else None)
    node, env = _build()
    result = subprocess.run([node, 'render-test.mjs'], cwd=_FRONTEND, env=env,
                            input=json.dumps(data), text=True, capture_output=True, check=True)
    if page:
        return body.split("<body", 1)[0] + '<body class="raute-ui">' + result.stdout + "</body></html>"
    # Keep the entire real legacy document, including headers and nested layout
    # elements. Fill only its React mount points; never introduce a second main.
    shell_html, main_html = result.stdout.split('<main class="content">', 1)
    tabs_html = main_html.rsplit('</main>', 1)[0].replace('<div id="react-platform"></div>', '')
    body = body.replace('<aside id="react-sidebar" class="side"></aside>', shell_html, 1)
    body = body.replace('<div id="react-client-tabs"></div>', tabs_html, 1)
    return re.sub(r'<script id="react-(?:shell|tabs)-data".*?</script>', '', body, flags=re.S)

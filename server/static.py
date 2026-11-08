"""Serves everything under web/: in-memory, gzip when accepted, ETag revalidation.

Only files that exist under web/ can be served, so server code, data and dotfiles
are never reachable. Files are re-read when their modification time changes, which
keeps local editing simple without a build step.
"""
import gzip
import hashlib
import mimetypes
from pathlib import Path

from aiohttp import web

TYPES = {'.mjs': 'text/javascript', '.js': 'text/javascript', '.webmanifest': 'application/manifest+json',
         '.svg': 'image/svg+xml', '.css': 'text/css', '.html': 'text/html', '.json': 'application/json'}
COMPRESSIBLE = ('text/', 'application/javascript', 'application/json', 'application/manifest+json', 'image/svg+xml')
SECURITY = {'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'same-origin',
            'X-Frame-Options': 'SAMEORIGIN', 'Permissions-Policy': 'camera=(), microphone=(), geolocation=()'}


class Static:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.cache = {}

    def load(self, relative):
        # Only the canonical spelling of a real file is served (and cached): no '//', './', '..' or dotfiles.
        parts = relative.split('/')
        if not relative or any(part in ('', '.', '..') or part.startswith('.') for part in parts):
            return None
        path = (self.root / relative).resolve()
        if self.root not in path.parents or not path.is_file():
            return None
        stamp = path.stat().st_mtime_ns
        hit = self.cache.get(relative)
        if hit and hit['stamp'] == stamp:
            return hit
        body = path.read_bytes()
        mime = TYPES.get(path.suffix) or mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        if mime.startswith('text/') or mime in ('application/json', 'application/manifest+json'):
            mime += '; charset=utf-8'
        entry = {'stamp': stamp, 'body': body, 'mime': mime, 'etag': '"' + hashlib.sha1(body).hexdigest()[:20] + '"',
                 'gzip': gzip.compress(body, 6, mtime=0) if mime.startswith(COMPRESSIBLE) and len(body) > 1024 else None}
        self.cache[relative] = entry
        return entry

    def response(self, request, relative):
        entry = self.load(relative)
        if entry is None:
            raise web.HTTPNotFound(text='Not found', headers=SECURITY)
        headers = {**SECURITY, 'ETag': entry['etag'], 'Cache-Control': 'no-cache', 'Vary': 'Accept-Encoding'}
        if request.headers.get('If-None-Match') == entry['etag']:
            return web.Response(status=304, headers=headers)
        body = entry['body']
        if entry['gzip'] and 'gzip' in request.headers.get('Accept-Encoding', ''):
            body = entry['gzip']
            headers['Content-Encoding'] = 'gzip'
        headers['Content-Type'] = entry['mime']
        return web.Response(body=body, headers=headers)

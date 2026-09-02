#!/usr/bin/env python3
"""Standalone HTTP upload server for ROS 2 media_play."""

import cgi
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.mov', '.avi', '.webm'}
MAX_SIZE = 500 * 1024 * 1024


class UploadHandler(BaseHTTPRequestHandler):
    upload_dir = Path(os.environ.get('MEDIA_PLAY_VIDEO_DIR', '~/media_play/videos')).expanduser()

    def do_GET(self):
        page = b'''<!doctype html><meta charset="utf-8"><title>media_play upload</title>
<h2>Video upload</h2><form method="post" enctype="multipart/form-data">
<input type="file" name="video" accept="video/*"><button>Upload</button></form>'''
        self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers(); self.wfile.write(page)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        if length > MAX_SIZE:
            self.send_error(413, 'file too large'); return
        ctype, _ = cgi.parse_header(self.headers.get('Content-Type', ''))
        if ctype != 'multipart/form-data':
            self.send_error(400, 'multipart/form-data required'); return
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers,
                                environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': self.headers['Content-Type']})
        if 'video' not in form or not form['video'].filename:
            self.send_error(400, 'video field required'); return
        upload = form['video']
        name = Path(upload.filename).name
        if Path(name).suffix.lower() not in VIDEO_EXTENSIONS:
            self.send_error(400, 'unsupported video extension'); return
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        destination = self.upload_dir / name
        index = 1
        while destination.exists():
            destination = self.upload_dir / f'{Path(name).stem}_{index}{Path(name).suffix}'
            index += 1
        destination.write_bytes(upload.file.read())
        self.send_response(200); self.end_headers(); self.wfile.write(destination.name.encode())

    def log_message(self, *_):
        pass


def main():
    port = int(os.environ.get('MEDIA_PLAY_UPLOAD_PORT', '8766'))
    HTTPServer(('0.0.0.0', port), UploadHandler).serve_forever()


if __name__ == '__main__':
    main()

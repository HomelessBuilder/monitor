#!/usr/bin/env python3
"""
Monitor web viewer — serves report files as formatted HTML on localhost:8765
Run with: python3 ~/monitor/web-server.py
"""

import http.server
import socketserver
import os
import re
from pathlib import Path
from datetime import datetime

MONITOR_DIR = Path.home() / "monitor"
REPORTS_DIR = MONITOR_DIR / "reports"
PORT = 8765

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; color: #e0e0e0; display: flex; min-height: 100vh; }
#sidebar { width: 280px; min-width: 280px; background: #16213e; padding: 20px; overflow-y: auto; border-right: 1px solid #0f3460; }
#sidebar h2 { color: #e94560; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 16px; }
#sidebar .section-label { color: #888; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; margin: 16px 0 8px; }
#sidebar a { display: block; padding: 8px 10px; border-radius: 4px; color: #a0b4c8; text-decoration: none; font-size: 13px; margin-bottom: 4px; }
#sidebar a:hover { background: #0f3460; color: #e0e0e0; }
#sidebar a.active { background: #e94560; color: #fff; }
#sidebar a.concern-link { color: #e94560; border: 1px solid #e9456040; }
#sidebar a.concern-link:hover { background: #e9456020; }
#content { flex: 1; padding: 32px 40px; max-width: 900px; overflow-y: auto; }
#content h1 { color: #e94560; font-size: 22px; margin-bottom: 24px; padding-bottom: 12px; border-bottom: 1px solid #0f3460; }
#content h2 { color: #a0c4ff; font-size: 16px; margin: 24px 0 12px; }
#content h3 { color: #c0d8f0; font-size: 14px; margin: 16px 0 8px; }
#content p { line-height: 1.7; margin-bottom: 12px; color: #c8d8e8; }
#content ul { margin: 8px 0 12px 20px; }
#content li { line-height: 1.7; color: #c8d8e8; margin-bottom: 4px; }
#content pre { background: #0d1b2a; border: 1px solid #0f3460; border-radius: 6px; padding: 16px; margin: 12px 0; overflow-x: auto; font-family: 'Courier New', monospace; font-size: 13px; line-height: 1.6; color: #a8d8a8; }
#content code { background: #0d1b2a; padding: 2px 6px; border-radius: 3px; font-family: 'Courier New', monospace; font-size: 13px; color: #a8d8a8; }
#content hr { border: none; border-top: 1px solid #0f3460; margin: 20px 0; }
#content strong { color: #e0e0e0; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; }
th { background: #0f3460; color: #a0c4ff; padding: 8px 12px; text-align: left; font-size: 13px; }
td { padding: 8px 12px; border-bottom: 1px solid #0f346060; font-size: 13px; color: #c8d8e8; }
.no-reports { color: #666; font-style: italic; }
.timestamp { color: #666; font-size: 12px; margin-bottom: 24px; }
"""

def md_to_html(text):
    lines = text.split('\n')
    html = []
    in_code = False
    in_table = False

    for line in lines:
        if line.startswith('```'):
            if in_code:
                html.append('</pre>')
                in_code = False
            else:
                html.append('<pre>')
                in_code = True
            continue

        if in_code:
            html.append(line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
            continue

        if line.startswith('| ') and '|' in line[2:]:
            if not in_table:
                html.append('<table>')
                in_table = True
                cells = [c.strip() for c in line.split('|') if c.strip()]
                html.append('<tr>' + ''.join(f'<th>{c}</th>' for c in cells) + '</tr>')
            elif re.match(r'^\|[-| ]+\|$', line):
                continue
            else:
                cells = [c.strip() for c in line.split('|') if c.strip()]
                html.append('<tr>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>')
            continue
        else:
            if in_table:
                html.append('</table>')
                in_table = False

        if line.startswith('# '):
            html.append(f'<h1>{line[2:]}</h1>')
        elif line.startswith('## '):
            html.append(f'<h2>{line[3:]}</h2>')
        elif line.startswith('### '):
            html.append(f'<h3>{line[4:]}</h3>')
        elif line.startswith('- ') or line.startswith('* '):
            content = inline_fmt(line[2:])
            html.append(f'<ul><li>{content}</li></ul>')
        elif line.startswith('---'):
            html.append('<hr>')
        elif line.strip() == '':
            html.append('')
        else:
            html.append(f'<p>{inline_fmt(line)}</p>')

    if in_table:
        html.append('</table>')
    if in_code:
        html.append('</pre>')

    # Merge consecutive <ul> items
    result = '\n'.join(html)
    result = re.sub(r'</ul>\s*<ul>', '', result)
    return result

def inline_fmt(text):
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    return text

def get_reports():
    if not REPORTS_DIR.exists():
        return [], None
    files = sorted(REPORTS_DIR.glob('*.md'), reverse=True)
    concerns = REPORTS_DIR / 'CONCERNS.md'
    report_files = [f for f in files if f.name != 'CONCERNS.md']
    concerns_file = concerns if concerns.exists() else None
    return report_files, concerns_file

def render_page(title, body_html, reports, concerns_file, active=None):
    sidebar_items = ''
    if concerns_file:
        sidebar_items += f'<div class="section-label">Concerns</div>'
        sidebar_items += f'<a href="/report/CONCERNS.md" class="concern-link">CONCERNS.md</a>'

    sidebar_items += '<div class="section-label">Reports</div>'
    if reports:
        for r in reports:
            active_class = ' active' if r.name == active else ''
            label = r.stem.replace('_', ' ')
            sidebar_items += f'<a href="/report/{r.name}"{" class=\"active\"" if active_class else ""}>{label}</a>'
    else:
        sidebar_items += '<span class="no-reports">No reports yet</span>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Monitor — {title}</title>
<style>{CSS}</style>
</head>
<body>
<div id="sidebar">
  <h2>Monitor</h2>
  {sidebar_items}
</div>
<div id="content">
{body_html}
</div>
</body>
</html>"""

class MonitorHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default request logging

    def do_GET(self):
        reports, concerns_file = get_reports()

        if self.path == '/' or self.path == '':
            if reports:
                self.send_response(302)
                self.send_header('Location', f'/report/{reports[0].name}')
                self.end_headers()
            else:
                body = '<h1>Monitor Reports</h1><p class="no-reports">No reports have been generated yet. The cron job runs hourly.</p>'
                page = render_page('No Reports', body, reports, concerns_file)
                self._send_html(page)

        elif self.path.startswith('/report/'):
            filename = self.path[len('/report/'):]
            filepath = REPORTS_DIR / filename
            if not filepath.exists() or not filepath.suffix == '.md':
                self._send_404()
                return
            content = filepath.read_text()
            body = md_to_html(content)
            mtime = datetime.fromtimestamp(filepath.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            body = f'<div class="timestamp">Last modified: {mtime}</div>' + body
            page = render_page(filename, body, reports, concerns_file, active=filename)
            self._send_html(page)

        else:
            self._send_404()

    def _send_html(self, html):
        encoded = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(encoded))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_404(self):
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b'Not found')

if __name__ == '__main__':
    with socketserver.TCPServer(('localhost', PORT), MonitorHandler) as httpd:
        print(f'Monitor viewer running at http://localhost:{PORT}')
        print('Press Ctrl+C to stop.')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\nStopped.')

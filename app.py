import os
import re
import tempfile
import logging
import json
import requests
from flask import Flask, request, abort, send_file, send_from_directory
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

app = Flask(__name__)
logging.basicConfig(format='[%(asctime)s] %(levelname)s: %(message)s', level=logging.INFO)

def normalize_video_id(raw_url: str) -> str:
    if not raw_url:
        abort(400, 'url 파라미터가 필요합니다.')
    parsed = urlparse(raw_url)
    qs = parse_qs(parsed.query)
    vid = qs.get('v', [None])[0]
    if not vid:
        m = re.match(r'^/(?:embed/|v/)?([A-Za-z0-9_-]{11})', parsed.path)
        vid = m.group(1) if m else None
    if not vid or not re.match(r'^[A-Za-z0-9_-]{11}$', vid):
        abort(400, '올바른 YouTube URL이 아닙니다.')
    return vid

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/download/video', methods=['GET','HEAD'])
def download_video():
    raw = request.args.get('url')
    video_id = normalize_video_id(raw)
    std_url = f'https://www.youtube.com/watch?v={video_id}'
    if request.method == 'HEAD':
        return '', 200, {'Content-Disposition': f'attachment; filename="{video_id}.mp4"'}
    # Launch headless Playwright to get streamingData
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(std_url, wait_until='networkidle')
        # Evaluate JS to extract ytInitialPlayerResponse
        player_response = page.evaluate("window.ytInitialPlayerResponse")
        browser.close()
    if not player_response or 'streamingData' not in player_response:
        abort(500, '스트리밍 데이터 추출 실패')
    streams = player_response['streamingData'].get('formats', []) + player_response['streamingData'].get('adaptiveFormats', [])
    # Filter progressive mp4
    prog = [s for s in streams if s.get('mimeType','').startswith('video/mp4') and 'videoOnly' not in s]
    if not prog:
        abort(500, '진행형(mp4) 스트림을 찾을 수 없습니다.')
    # pick highest resolution
    best = sorted(prog, key=lambda s: s.get('height',0))[-1]
    url = best.get('url')
    if not url:
        abort(500, '스트림 URL 없음')
    # download via requests
    response = requests.get(url, stream=True)
    if response.status_code != 200:
        abort(500, '비디오 다운로드 실패')
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    for chunk in response.iter_content(chunk_size=8192):
        tmp.write(chunk)
    tmp.close()
    resp = send_file(tmp.name, as_attachment=True, download_name=f'{video_id}.mp4')
    os.remove(tmp.name)
    return resp

@app.route('/download/thumbnail', methods=['GET','HEAD'])
def download_thumbnail():
    raw = request.args.get('url')
    video_id = normalize_video_id(raw)
    if request.method == 'HEAD':
        return '', 200, {'Content-Disposition': f'attachment; filename="{video_id}.jpg"'}
    std_url = f'https://www.youtube.com/watch?v={video_id}'
    # extract thumbnail via requests and regex
    resp = requests.get(std_url)
    m = re.search(r'"thumbnailUrl":"([^"]+)"', resp.text)
    if not m:
        abort(500, '썸네일 URL 추출 실패')
    thumb_url = m.group(1).replace('\u0026', '&')
    r = requests.get(thumb_url, stream=True)
    if r.status_code != 200:
        abort(500, '썸네일 다운로드 실패')
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
    for c in r.iter_content(1024):
        tmp.write(c)
    tmp.close()
    out = send_file(tmp.name, as_attachment=True, download_name=f'{video_id}.jpg')
    os.remove(tmp.name)
    return out

if __name__=='__main__':
    # Ensure Playwright browsers are installed: playwright install
    app.run(host='0.0.0.0', port=5000, debug=True)

import os
import re
import tempfile
import logging
from flask import Flask, request, abort, send_file, send_from_directory
from yt_dlp import YoutubeDL
from pytube import YouTube
import requests
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)
logging.basicConfig(format='[%(asctime)s] %(levelname)s: %(message)s', level=logging.INFO)

# yt-dlp options for public videos
YDL_OPTS = {
    'format': 'bestvideo[ext=mp4]+bestaudio/best',
    'outtmpl': os.path.join(tempfile.gettempdir(), '%(id)s.%(ext)s'),
    'quiet': True,
    'no_warnings': True,
}

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
    vid = normalize_video_id(raw)
    std_url = f'https://www.youtube.com/watch?v={vid}'
    out_path = os.path.join(tempfile.gettempdir(), f'{vid}.mp4')

    if request.method == 'HEAD':
        return '', 200, {'Content-Disposition': f'attachment; filename="{vid}.mp4"'}

    app.logger.info(f'[video] Downloading {std_url}')
    with YoutubeDL(YDL_OPTS) as ydl:
        try:
            ydl.extract_info(std_url, download=True)
        except Exception as e:
            app.logger.error(f'[video] yt-dlp failed: {e}', exc_info=True)
            abort(500, f'다운로드 실패: {e}')

    if not os.path.exists(out_path):
        abort(500, '다운로드 후 파일을 찾을 수 없습니다.')

    resp = send_file(out_path, as_attachment=True, download_name=f'{vid}.mp4')
    try: os.remove(out_path)
    except: pass
    return resp

@app.route('/download/thumbnail', methods=['GET','HEAD'])
def download_thumbnail():
    raw = request.args.get('url')
    vid = normalize_video_id(raw)
    std_url = f'https://www.youtube.com/watch?v={vid}'
    filename = f'{vid}.jpg'

    if request.method == 'HEAD':
        return '',200,{'Content-Disposition':f'attachment; filename="{filename}"'}

    # pytube for thumbnail
    yt = YouTube(std_url)
    thumb_url = yt.thumbnail_url
    r = requests.get(thumb_url, stream=True)
    if r.status_code!=200:
        abort(500,'썸네일 요청 실패')

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
    for c in r.iter_content(1024): tmp.write(c)
    tmp.close()

    resp = send_file(tmp.name, as_attachment=True, download_name=filename)
    try: os.remove(tmp.name)
    except: pass
    return resp

if __name__=='__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

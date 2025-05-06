from flask import Flask, request, send_file, abort, make_response
import subprocess
import tempfile
import os
import requests
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)

@app.route('/')
def home():
    return send_file('index.html')

@app.route('/download/video', methods=['GET','HEAD'])
def download_video():
    url = request.args.get('url')
    quality = request.args.get('quality', 'highest')
    if not url:
        abort(400, 'url 파라미터가 필요합니다')

    # HEAD 요청: 메타 정보만 반환
    if request.method == 'HEAD':
        # youtube-dl로 정보 조회
        cmd = ['youtube-dl', '--skip-download', '--print-json', url]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            # youtube-dl JSON에는 filesize available?
            # We parse filesize if present
            info = result.stdout
            # For simplicity, return filename header only
            qs = parse_qs(urlparse(url).query)
            video_id = qs.get('v', ['video'])[0]
            filename = f"{video_id}.mp4"
            headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
            return ('', 200, headers)
        except subprocess.CalledProcessError as e:
            abort(500, f"메타 정보 조회 실패: {e.stderr}")

    # GET 요청: 실제 다운로드
    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, 'video.mp4')
        cmd = ['youtube-dl', '-f', 'bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best', '-o', out_path, url]
        if quality != 'highest':
            # 특정 품질 선택 (예: 720p)
            cmd = ['youtube-dl', '-f', f'bestvideo[height<={quality.replace("p","")}]+bestaudio/best', '-o', out_path, url]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return send_file(out_path, as_attachment=True, attachment_filename='video.mp4')
        except subprocess.CalledProcessError as e:
            abort(500, f"다운로드 실패: {e.stderr}")

@app.route('/download/thumbnail', methods=['GET','HEAD'])
def download_thumbnail():
    url = request.args.get('url')
    if not url:
        abort(400, 'url 파라미터가 필요합니다')

    # thumbnail URL 추출
    # youtube-dl로 metadata
    cmd = ['youtube-dl', '--skip-download', '--print-json', url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        import json
        info = json.loads(result.stdout)
        thumb_url = info.get('thumbnail')
    except Exception as e:
        abort(500, f"썸네일 URL 조회 실패: {e}")

    filename = os.path.basename(urlparse(thumb_url).path)

    if request.method == 'HEAD':
        headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
        return ('', 200, headers)

    resp = requests.get(thumb_url, timeout=10)
    if resp.status_code != 200:
        abort(404, '썸네일을 가져올 수 없습니다')
    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmpf:
        tmpf.write(resp.content)
        tmpf.flush()
        return send_file(tmpf.name, as_attachment=True, attachment_filename=filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

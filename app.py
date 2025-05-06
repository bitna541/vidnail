import re
import os
import tempfile
import subprocess
import sys
from flask import Flask, request, abort, send_file
from pytube import YouTube

app = Flask(__name__)

@app.route('/download/video', methods=['GET', 'HEAD'])
def download_video():
    raw_url = request.args.get('url')
    if not raw_url:
        abort(400, 'url 파라미터가 필요합니다')
    m = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', raw_url)
    if not m:
        abort(400, '올바른 YouTube URL이 아닙니다.')
    video_id = m.group(1)
    url = f'https://www.youtube.com/watch?v={video_id}'
    quality = request.args.get('quality', 'highest')
    out_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    out_file_path = out_file.name
    out_file.close()

    # 포맷 설정
    if quality == 'highest':
        fmt = 'best'
    else:
        # 예: '720p' -> height<=720
        height = quality.replace('p', '')
        fmt = f'bestvideo[height<={height}]+bestaudio/best'

    cmd = ['yt-dlp', '-f', fmt, '-o', out_file_path, url]

    if request.method == 'HEAD':
        return ('', 200, {'Content-Disposition': f'attachment; filename="{video_id}.mp4"'})

    try:
        app.logger.info(f"[download_video] Running command: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        app.logger.info(f"[download_video] Sending file {out_file_path}")
        return send_file(out_file_path, as_attachment=True, download_name=f"{video_id}.mp4")
    except subprocess.CalledProcessError as e:
        abort(500, f'다운로드 실패: {{e}}')
    finally:
        # 임시 파일은 send_file 이후에 삭제될 수 있도록 두거나, 배포 환경에서 정리
        pass

@app.route('/download/thumbnail', methods=['GET', 'HEAD'])
def download_thumbnail():
    raw_url = request.args.get('url')
    if not raw_url:
        abort(400, 'url 파라미터가 필요합니다')
    m = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', raw_url)
    if not m:
        abort(400, '올바른 YouTube URL이 아닙니다.')
    video_id = m.group(1)
    yt = YouTube(f'https://www.youtube.com/watch?v={video_id}')
    thumb_url = yt.thumbnail_url
    filename = f'{video_id}.jpg'

    if request.method == 'HEAD':
        return ('', 200, {'Content-Disposition': f'attachment; filename="{filename}"'})

    resp = __import__('requests').get(thumb_url, stream=True)
    if resp.status_code != 200:
        abort(500, '썸네일 요청 실패')

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
    for chunk in resp.iter_content(1024):
        tmp.write(chunk)
    tmp.close()

    app.logger.info(f"[download_thumbnail] Sending file {tmp.name}")
    response = send_file(tmp.name, as_attachment=True, download_name=filename)
    try:
        os.remove(tmp.name)
    except:
        pass
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

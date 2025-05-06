from flask import Flask, request, abort, send_file
from pytube import YouTube
import re
import tempfile
import os
import sys

app = Flask(__name__)

def normalize_url(raw_url):
    # 비디오 ID만 추출하여 표준 URL로 재생성
    m = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', raw_url or '')
    if not m:
        abort(400, '올바른 YouTube URL이 아닙니다.')
    video_id = m.group(1)
    return f'https://www.youtube.com/watch?v={video_id}', video_id

@app.route('/download/video', methods=['GET', 'HEAD'])
def download_video():
    raw_url = request.args.get('url')
    if not raw_url:
        abort(400, 'url 파라미터가 필요합니다')

    url, video_id = normalize_url(raw_url)
    quality = request.args.get('quality', 'highest')

    yt = YouTube(url)
    # 스트림 선택
    if quality == 'highest':
        stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
    else:
        # e.g. '720p' -> 720
        height = int(quality.replace('p', ''))
        stream = yt.streams.filter(progressive=True, file_extension='mp4', resolution=f'{height}p').first()
    if not stream:
        abort(400, '해당 품질의 스트림을 찾을 수 없습니다.')

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    tmp.close()
    try:
        stream.download(output_path=os.path.dirname(tmp.name), filename=os.path.basename(tmp.name))
    except Exception as e:
        abort(500, f'다운로드 실패: {e}')

    if request.method == 'HEAD':
        headers = {'Content-Disposition': f'attachment; filename="{video_id}.mp4"'}
        return ('', 200, headers)

    print(f"[download_video] Sending file {tmp.name}")
    sys.stdout.flush()
    return send_file(tmp.name, as_attachment=True, download_name=f"{video_id}.mp4")

@app.route('/download/thumbnail', methods=['GET', 'HEAD'])
def download_thumbnail():
    raw_url = request.args.get('url')
    if not raw_url:
        abort(400, 'url 파라미터가 필요합니다')

    url, video_id = normalize_url(raw_url)
    yt = YouTube(url)
    thumb_url = yt.thumbnail_url
    filename = f'{video_id}.jpg'

    if request.method == 'HEAD':
        headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
        return ('', 200, headers)

    resp = __import__('requests').get(thumb_url, stream=True)
    if resp.status_code != 200:
        abort(500, '썸네일 요청 실패')
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
    for chunk in resp.iter_content(1024):
        tmp.write(chunk)
    tmp.close()

    print(f"[download_thumbnail] Sending file {tmp.name}")
    sys.stdout.flush()
    response = send_file(tmp.name, as_attachment=True, download_name=filename)
    try:
        os.remove(tmp.name)
    except:
        pass
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

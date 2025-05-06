import os
import re
import tempfile
from flask import Flask, request, abort, send_file, send_from_directory
from pytube import YouTube
import requests
import logging

app = Flask(__name__)
logging.basicConfig(
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    level=logging.INFO
)

# Serve index.html at root
@app.route('/')
def index():
    return send_file('index.html')

def normalize_video_id(raw_url: str) -> str:
    m = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', raw_url or '')
    if not m:
        abort(400, '올바른 YouTube URL이 아닙니다.')
    return m.group(1)

@app.route('/download/video', methods=['GET', 'HEAD'])
def download_video():
    raw_url = request.args.get('url')
    if not raw_url:
        abort(400, 'url 파라미터가 필요합니다.')

    video_id = normalize_video_id(raw_url)
    std_url = f'https://www.youtube.com/watch?v={video_id}'
    quality = request.args.get('quality', 'highest')

    yt = YouTube(std_url)
    streams = yt.streams.filter(progressive=True, file_extension='mp4')                         .order_by('resolution').desc()
    if quality != 'highest':
        streams = streams.filter(res=quality)
    stream = streams.first()
    if not stream:
        abort(500, '요청하신 포맷의 스트림을 찾을 수 없습니다.')

    if request.method == 'HEAD':
        headers = {'Content-Disposition': f'attachment; filename="{video_id}.mp4"'}
        return '', 200, headers

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    out_path = tmp.name
    tmp.close()

    try:
        app.logger.info(f'[download_video] 다운로드 시작: {std_url}')
        yt.streams.get_by_itag(stream.itag).download(
            output_path=os.path.dirname(out_path),
            filename=os.path.basename(out_path)
        )
    except Exception as e:
        app.logger.error(f'[download_video] 실패: {e}', exc_info=True)
        abort(500, f'다운로드 실패: {e}')

    response = send_file(out_path, as_attachment=True, download_name=f'{video_id}.mp4')
    try:
        os.remove(out_path)
    except:
        pass
    return response

@app.route('/download/thumbnail', methods=['GET', 'HEAD'])
def download_thumbnail():
    raw_url = request.args.get('url')
    if not raw_url:
        abort(400, 'url 파라미터가 필요합니다.')

    video_id = normalize_video_id(raw_url)
    std_url = f'https://www.youtube.com/watch?v={video_id}'
    yt = YouTube(std_url)
    thumb_url = yt.thumbnail_url
    filename = f'{video_id}.jpg'

    if request.method == 'HEAD':
        return '', 200, {'Content-Disposition': f'attachment; filename="{filename}"'}

    resp = requests.get(thumb_url, stream=True)
    if resp.status_code != 200:
        abort(500, '썸네일 요청 실패')

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
    for chunk in resp.iter_content(1024):
        tmp.write(chunk)
    tmp.close()

    response = send_file(tmp.name, as_attachment=True, download_name=filename)
    try:
        os.remove(tmp.name)
    except:
        pass
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

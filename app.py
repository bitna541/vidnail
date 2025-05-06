from flask import Flask, request, send_file, abort, make_response
import re
from pytube import YouTube
import requests, tempfile, os
from urllib.parse import unquote, urlparse, parse_qs

app = Flask(__name__)

@app.route('/')
def home():
    return send_file('index.html')

@app.route('/download/video', methods=['GET', 'HEAD'])
def download_video():
    # 1) 원본 URL을 가져와서
    raw_url = request.args.get('url')
    if not raw_url:
        abort(400, 'url 파라미터가 필요합니다')
    # 2) URL 디코딩
    raw_url = unquote(raw_url)
    # 3) URL 정규화: 비디오 ID만 추출하여 표준 URL로 재생성
    m = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', raw_url or '')
    if not m:
        abort(400, '올바른 YouTube URL이 아닙니다.')
    video_id = m.group(1)
    url = f'https://www.youtube.com/watch?v={video_id}'

    # HEAD 요청 분기: 스트림 탐색 없이 헤더만 반환
    if request.method == 'HEAD':
        filename = f"{video_id}.mp4"
        yt = YouTube(url)
        stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
        filesize = getattr(stream, 'filesize', None)
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
        if filesize is not None:
            headers['Content-Length'] = str(filesize)
        return ('', 200, headers)

    # GET 요청: 실제 다운로드
    quality = request.args.get('quality', 'highest')
    try:
        yt = YouTube(url)
        streams = yt.streams.filter(progressive=True, file_extension='mp4')
        if quality != 'highest':
            stream = streams.filter(res=quality).first() or streams.order_by('resolution').desc().first()
        else:
            stream = streams.order_by('resolution').desc().first()
        if not stream:
            abort(404, '요청한 품질의 스트림을 찾을 수 없습니다')

        with tempfile.TemporaryDirectory() as tmp:
            video_path = stream.download(output_path=tmp, filename='video.mp4')
            response = make_response(send_file(video_path, as_attachment=True))
            safe_title = yt.title.replace('/', '_').replace('\\', '_')
            response.headers['X-Filename'] = f"{safe_title}.mp4"
            return response
    except Exception as e:
        abort(500, f"다운로드 실패: {e}")

@app.route('/download/thumbnail', methods=['GET'])
def download_thumbnail():
    raw_url = request.args.get('url')
    if not raw_url:
        abort(400, 'url 파라미터가 필요합니다')
    # 디코딩
    raw_url = unquote(raw_url)
    try:
        yt = YouTube(raw_url)
        thumb_url = yt.thumbnail_url
        resp = requests.get(thumb_url, timeout=10)
        if resp.status_code != 200:
            abort(404, '썸네일을 가져올 수 없습니다')
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmpf:
            tmpf.write(resp.content)
            tmpf.flush()
            filename = f"{video_id}.jpg"
            response = make_response(send_file(tmpf.name, as_attachment=True))
            response.headers['X-Filename'] = filename
        os.unlink(tmpf.name)
        return response
    except Exception as e:
        abort(500, f"썸네일 다운로드 실패: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

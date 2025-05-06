
import re
from flask import Flask, request, send_file, abort, make_response
from pytube import YouTube
import requests, tempfile, os

app = Flask(__name__)

@app.route('/')
def home():
    return send_file('index.html')

@app.route('/download/video', methods=['GET', 'HEAD'])
def download_video():
    # 1) 원본 URL을 가져와서
    raw_url = request.args.get('url')
    # 2) URL 정규화: 비디오 ID만 추출하여 표준 URL로 재생성
    raw_m = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', raw_url or '')
    if not raw_m:
        abort(400, '올바른 YouTube URL이 아닙니다.')
    raw_video_id = raw_m.group(1)
    url = f'https://www.youtube.com/watch?v={raw_video_id}'
    quality = request.args.get('quality', 'highest')

    # HEAD 분기 로직 등 이하 기존 로직 그대로 이어집니다...
    if request.method == 'HEAD':
        # 헤더만 반환하는 예시: 파일명과 크기 등을 설정
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(url).query)
        video_id = qs.get('v', ['video'])[0]
        filename = f"{video_id}.mp4"
        return ('', 200, {
            'Content-Disposition': f'attachment; filename="{filename}"'
        })

    # 나머지 다운로드 로직...
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

# (thumbnail endpoint, __main__ 부분은 기존과 동일)
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

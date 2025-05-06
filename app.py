from flask import Flask, request, send_file, abort, make_response
from pytube import YouTube
import requests, tempfile, os
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)

@app.route('/')
def home():
    return send_file('index.html')

@app.route('/download/video', methods=['GET','HEAD'])
def download_video():
    # 1) 원본 URL을 가져와서
    raw_url = request.args.get('url')
    quality = request.args.get('quality', 'highest')
    if not raw_url:
        abort(400, 'url 파라미터가 필요합니다')

    # URL normalization: extract video ID and reconstruct standard URL
    parsed = urlparse(raw_url)
    if parsed.hostname in ('youtu.be', 'www.youtu.be'):
        video_id = parsed.path.lstrip('/')
    else:
        qs = parse_qs(parsed.query)
        video_id = qs.get('v', [None])[0]
    if not video_id:
        abort(400, '유효한 유튜브 URL이 아닙니다')
    url = f"https://www.youtube.com/watch?v={video_id}"

    # HEAD 요청: 스트림 탐색 없이 헤더만 반환
    if request.method == 'HEAD':
        filename = f"{video_id}.mp4"
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
        return ('', 200, headers)

    # GET 요청: 실제 다운로드
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

@app.route('/download/thumbnail', methods=['GET','HEAD'])
def download_thumbnail():
    raw_url = request.args.get('url')
    if not raw_url:
        abort(400, 'url 파라미터가 필요합니다')
    parsed = urlparse(raw_url)
    if parsed.hostname in ('youtu.be', 'www.youtu.be'):
        video_id = parsed.path.lstrip('/')
    else:
        qs = parse_qs(parsed.query)
        video_id = qs.get('v', [None])[0]
    if not video_id:
        abort(400, '유효한 유튜브 URL이 아닙니다')
    url = f"https://www.youtube.com/watch?v={video_id}"

    # HEAD 요청: 헤더만 반환
    if request.method == 'HEAD':
        filename = f"{video_id}.jpg"
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
        return ('', 200, headers)

    # GET 요청: 썸네일 다운로드
    try:
        yt = YouTube(url)
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
    # 모든 인터페이스에서 5000 포트로 디버그 모드 실행
    app.run(host='0.0.0.0', port=5000, debug=True)

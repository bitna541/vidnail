from flask import Flask, request, send_file, abort, make_response
from pytube import YouTube
import pytube.request as pytube_request
import requests, tempfile, os
from urllib.parse import urlparse, parse_qs

# Apply browser-like User-Agent to pytube request headers
# Use HEADERS attribute from pytube.request module
pytube_request.HEADERS['User-Agent'] = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/113.0.0.0 Safari/537.36'
)

app = Flask(__name__)

@app.route('/')
def home():
    return send_file('index.html')

@app.route('/download/video', methods=['GET','HEAD'])
def download_video():
    # HEAD 분기: 스트림 탐색 없이 헤더만 반환
    if request.method == 'HEAD':
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(request.args.get('url', '')).query)
        video_id = qs.get('v', ['video'])[0]
        filename = f"{video_id}.mp4"
        return ('', 200, {
            'Content-Disposition': f'attachment; filename="{filename}"'
        })

    url = request.args.get('url')
    quality = request.args.get('quality', 'highest')
    if not url:
        abort(400, 'url 파라미터가 필요합니다')

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

@app.route('/download/thumbnail')
def download_thumbnail():
    url = request.args.get('url')
    if not url:
        abort(400, 'url 파라미터가 필요합니다')
    try:
        yt = YouTube(url)
        thumb_url = yt.thumbnail_url
        resp = requests.get(thumb_url, timeout=10)
        if resp.status_code != 200:
            abort(404, '썸네일을 가져올 수 없습니다')
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmpf:
            tmpf.write(resp.content)
            tmpf.flush()
            filename = f"{yt.title.replace('/', '_').replace('\\', '_')}.jpg"
            response = make_response(send_file(tmpf.name, as_attachment=True))
            response.headers['X-Filename'] = filename
        os.unlink(tmpf.name)
        return response
    except Exception as e:
        abort(500, f"썸네일 다운로드 실패: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

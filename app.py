from flask import Flask, request, send_file, abort, make_response, Response
from pytube import YouTube
import requests, tempfile, os

app = Flask(__name__)

@app.route('/')
def home():
    return send_file('index.html')

@app.route('/download/video', methods=['GET', 'HEAD'])
def download_video():
    url = request.args.get('url')
    quality = request.args.get('quality', 'highest')
    if not url:
        abort(400, 'url 파라미터가 필요합니다')

    # 1) 스트림 객체만 찾기
    try:
        yt = YouTube(url)
    except Exception:
        abort(400, '잘못된 유튜브 URL입니다')

    streams = yt.streams.filter(progressive=True, file_extension='mp4')
    if quality != 'highest':
        stream = streams.filter(res=quality).first() \
                 or streams.order_by('resolution').desc().first()
    else:
        stream = streams.order_by('resolution').desc().first()

    if not stream:
        abort(404, '요청한 품질의 스트림을 찾을 수 없습니다')

    # 2) 파일 이름과 크기 확보
    safe_title = yt.title.replace('/', '_').replace('\\', '_')
    filename = f"{safe_title}.mp4"
    try:
        filesize = stream.filesize
    except Exception:
        filesize = None

    # 3) HEAD 요청인 경우 헤더만 반환
    if request.method == 'HEAD':
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
        if filesize:
            headers['Content-Length'] = str(filesize)
        return ('', 200, headers)

    # 4) GET 요청인 경우 실제 다운로드
    tmp_dir = tempfile.TemporaryDirectory()
    video_path = stream.download(output_path=tmp_dir.name, filename='video.mp4')
    response = make_response(send_file(video_path, as_attachment=True))
    response.headers['X-Filename'] = filename
    tmp_dir.cleanup()
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

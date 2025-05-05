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

    # — HEAD 요청 처리
    if request.method == 'HEAD':
        try:
            yt = YouTube(url)
            streams = yt.streams.filter(progressive=True, file_extension='mp4')
            stream = (streams.filter(res=quality).first()
                      if quality!='highest'
                      else streams.order_by('resolution').desc().first())
            if not stream:
                abort(404, '요청한 품질의 스트림을 찾을 수 없습니다')
            filename = yt.title.replace('/', '_').replace('\\','_') + '.mp4'
            filesize = stream.filesize
        except Exception:
            abort(400, '스트림 정보를 가져오지 못했습니다')
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
        if filesize:
            headers['Content-Length'] = str(filesize)
        return ('', 200, headers)

    # — GET 요청 처리 (기존 로직)
    with tempfile.TemporaryDirectory() as tmp_dir:
        video_path = stream.download(
            output_path=tmp_dir, filename='video.mp4'
        )
        response = make_response(
            send_file(video_path, as_attachment=True)
        )
        response.headers['X-Filename'] = filename
    return response


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

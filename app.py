from flask import Flask, request, send_file, abort, make_response
from pytube import YouTube
import subprocess, tempfile, os, re, requests

app = Flask(__name__)

@app.route('/')
def home():
    return send_file('index.html')

@app.route('/download/video', methods=['GET', 'HEAD'])
def download_video():
    raw_url = request.args.get('url')
    quality = request.args.get('quality', 'highest')
    if not raw_url:
        abort(400, 'url 파라미터가 필요합니다')

    m = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', raw_url)
    if not m:
        abort(400, '올바른 YouTube URL이 아닙니다.')
    video_id = m.group(1)
    url = f'https://www.youtube.com/watch?v={video_id}'

    # HEAD 요청 처리
    if request.method == 'HEAD':
        headers = {
            'Content-Disposition': f'attachment; filename="{video_id}.mp4"'
        }
        return ('', 200, headers)

    # 비디오 다운로드
    out_dir = tempfile.mkdtemp()
    out_path = os.path.join(out_dir, f'{video_id}.mp4')
    cmd = ['yt-dlp', '-f', 'bestvideo[ext=mp4]+bestaudio/best', '-o', out_path, url]
    if quality != 'highest':
        height = quality.replace('p', '')
        cmd = ['yt-dlp', '-f', f'bestvideo[height<={height}]+bestaudio/best', '-o', out_path, url]

    try:
        subprocess.run(cmd, check=True)
        return send_file(out_path, as_attachment=True, download_name=f'{video_id}.mp4')
    except subprocess.CalledProcessError as e:
        abort(500, f'다운로드 실패: {e.stderr}')
    finally:
        try:
            os.remove(out_path)
        except:
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
        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
        return ('', 200, headers)

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

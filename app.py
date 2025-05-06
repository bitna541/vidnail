from flask import Flask, request, send_file, abort, make_response
import subprocess
import tempfile
import os

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

    # 파일 임시 경로 생성
    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, 'video.mp4')
        # yt-dlp로 다운로드 (youtube-dl 대신 yt-dlp 사용)
        if quality == 'highest':
            cmd = ['yt-dlp', '-f', 'bestvideo[ext=mp4]+bestaudio/best', '-o', out_path, url]
        else:
            # 예: 720p이면 height<=720
            height = quality.replace('p', '')
            cmd = ['yt-dlp', '-f', f'bestvideo[height<={height}]+bestaudio/best', '-o', out_path, url]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return send_file(out_path, as_attachment=True)
        except subprocess.CalledProcessError as e:
            abort(500, f"다운로드 실패: {e.stderr}")

@app.route('/download/thumbnail', methods=['GET', 'HEAD'])
def download_thumbnail():
    url = request.args.get('url')
    if not url:
        abort(400, 'url 파라미터가 필요합니다')

    # yt-dlp로 썸네일 URL 추출
    try:
        # yt-dlp --get-thumbnail
        result = subprocess.run(['yt-dlp', '--get-thumbnail', url],
                                capture_output=True, text=True, check=True)
        thumb_url = result.stdout.strip()
        # 요청하여 파일로 저장
        resp = requests.get(thumb_url, timeout=10)
        if resp.status_code != 200:
            abort(404, '썸네일을 가져올 수 없습니다')
        tmpf = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        tmpf.write(resp.content)
        tmpf.flush()
        filename = os.path.basename(thumb_url)
        response = make_response(send_file(tmpf.name, as_attachment=True))
        response.headers['X-Filename'] = filename
        os.unlink(tmpf.name)
        return response
    except Exception as e:
        abort(500, f"썸네일 다운로드 실패: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

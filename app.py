# app.py

import os
import re
import sys
import tempfile
from flask import Flask, request, abort, send_file
from pytube import YouTube
from pytube import request as pytube_request
import requests
import logging

# ── 1) Pytube User-Agent 덮어쓰기 ────────────────────────────────
pytube_request.default_headers = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/112.0.0.0 Safari/537.36'
    )
}

app = Flask(__name__)
logging.basicConfig(
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    level=logging.INFO
)


def normalize_video_id(raw_url: str) -> str:
    """URL에서 11자리 비디오 ID만 뽑아서 반환"""
    m = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', raw_url or '')
    if not m:
        abort(400, '올바른 YouTube URL이 아닙니다.')
    return m.group(1)


@app.route('/download/video', methods=['GET', 'HEAD'])
def download_video():
    # 1) URL 파라미터
    raw_url = request.args.get('url')
    if not raw_url:
        abort(400, 'url 파라미터가 필요합니다.')

    # 2) 비디오 ID 정규화
    video_id = normalize_video_id(raw_url)
    std_url = f'https://www.youtube.com/watch?v={video_id}'
    quality = request.args.get('quality', 'highest')

    # 3) Pytube 객체 (쿠키 사용 옵션 추가)
    yt = YouTube(
        std_url,
        cookies='cookies.txt',       # 2번 방식: 추출해 둔 cookies.txt (선택사항)
        # use_oauth=True,            # (옵션) OAuth 토큰 이용
        # allow_oauth_cache=True
    )

    # 4) 스트림 선택
    streams = yt.streams.filter(
        progressive=True,
        file_extension='mp4'
    ).order_by('resolution').desc()
    if quality != 'highest':
        # e.g. "720p" -> height<=720
        height = int(quality.replace('p', ''))
        streams = streams.filter(res=quality)
    stream = streams.first()
    if not stream:
        abort(500, '요청하신 포맷의 스트림을 찾을 수 없습니다.')

    # 5) 임시파일 경로
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    out_path = tmp.name
    tmp.close()

    # 6) 실제 다운로드
    try:
        app.logger.info(f'[download_video] 다운로드 시작: {std_url} -> {out_path}')
        yt.streams.get_by_itag(stream.itag).download(
            output_path=os.path.dirname(out_path),
            filename=os.path.basename(out_path)
        )
    except Exception as e:
        app.logger.error(f'[download_video] 실패: {e}', exc_info=True)
        abort(500, f'다운로드 실패: {e}')

    # 7) HEAD 요청만 왔을 때
    if request.method == 'HEAD':
        headers = {'Content-Disposition': f'attachment; filename="{video_id}.mp4"'}
        return ('', 200, headers)

    # 8) 실제 파일 전송
    app.logger.info(f'[download_video] 전송: {out_path}')
    response = send_file(
        out_path,
        as_attachment=True,
        download_name=f'{video_id}.mp4'
    )
    # 클린업
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
    yt = YouTube(std_url, cookies='cookies.txt')
    thumb_url = yt.thumbnail_url
    filename = f'{video_id}.jpg'

    if request.method == 'HEAD':
        headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
        return ('', 200, headers)

    resp = requests.get(thumb_url, stream=True)
    if resp.status_code != 200:
        abort(500, '썸네일 요청 실패')

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
    for chunk in resp.iter_content(1024):
        tmp.write(chunk)
    tmp.close()

    response = send_file(
        tmp.name,
        as_attachment=True,
        download_name=filename
    )
    try:
        os.remove(tmp.name)
    except:
        pass
    return response


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

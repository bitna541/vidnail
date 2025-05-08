from flask import Flask, jsonify, request, send_file
import os
import uuid
import shutil
import zipfile
import time
import threading
import re
import yt_dlp
import requests
from werkzeug.utils import secure_filename
from pathlib import Path

app = Flask(__name__, static_folder='static')

# 임시 디렉토리 설정
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')
# 최대 파일 보존 시간 (초)
MAX_FILE_AGE = 300  # 5분

# 임시 디렉토리가 없으면 생성
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

def clean_temp_files():
    """오래된 임시 파일 주기적으로 삭제"""
    while True:
        now = time.time()
        for filename in os.listdir(TEMP_DIR):
            file_path = os.path.join(TEMP_DIR, filename)
            # 파일의 생성시간이 MAX_FILE_AGE보다 오래되었으면 삭제
            if os.path.isfile(file_path) and now - os.path.getctime(file_path) > MAX_FILE_AGE:
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")
            # 디렉토리도 삭제
            elif os.path.isdir(file_path) and now - os.path.getctime(file_path) > MAX_FILE_AGE:
                try:
                    shutil.rmtree(file_path)
                except Exception as e:
                    print(f"Error deleting directory {file_path}: {e}")
        time.sleep(60)  # 1분마다 체크

# 백그라운드에서 임시 파일 정리 스레드 시작
cleaning_thread = threading.Thread(target=clean_temp_files, daemon=True)
cleaning_thread.start()

def sanitize_filename(filename):
    """파일명에서 유효하지 않은 문자 제거"""
    # 파일 이름에 사용할 수 없는 문자 제거 및 대체
    filename = re.sub(r'[\\/*?:"<>|]', "", filename)
    # 긴 이름은 잘라내기
    if len(filename) > 100:
        filename = filename[:97] + "..."
    return filename

def get_video_info(url):
    """유튜브 비디오 또는 재생목록 정보 가져오기"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # 재생목록인지 확인
            if 'entries' in info:
                # 재생목록 정보
                first_video = None
                if len(info['entries']) > 0:
                    # 첫 번째 동영상 정보 가져오기
                    first_video_url = info['entries'][0]['url']
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl2:
                        first_video = ydl2.extract_info(first_video_url, download=False)
                
                return {
                    'is_playlist': True,
                    'playlist_title': info.get('title', '재생목록'),
                    'video_count': len(info['entries']),
                    'first_video_thumbnail': first_video.get('thumbnail') if first_video else '',
                    'videos': [{'id': entry.get('id'), 'title': entry.get('title')} for entry in info['entries']]
                }
            else:
                # 단일 비디오 정보
                duration_seconds = info.get('duration', 0)
                minutes, seconds = divmod(duration_seconds, 60)
                hours, minutes = divmod(minutes, 60)
                
                if hours > 0:
                    duration = f"{hours}:{minutes:02d}:{seconds:02d}"
                else:
                    duration = f"{minutes}:{seconds:02d}"
                
                return {
                    'is_playlist': False,
                    'title': info.get('title', '제목 없음'),
                    'thumbnail_url': info.get('thumbnail', ''),
                    'duration': duration,
                    'uploader': info.get('uploader', '업로더 정보 없음'),
                    'video_id': info.get('id'),
                }
    except Exception as e:
        print(f"Error fetching video info: {e}")
        return {'error': str(e)}

def download_video(url, output_path, is_single_video=True):
    """최고 화질의 비디오 다운로드"""
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_path,
        'quiet': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return info

def download_thumbnail(url, output_path):
    """썸네일 이미지 다운로드"""
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(output_path, 'wb') as f:
            shutil.copyfileobj(response.raw, f)
        return True
    return False

@app.route('/api/info', methods=['POST'])
def get_info():
    """URL에서 비디오 정보 가져오기"""
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'URL이 제공되지 않았습니다.'})
    
    info = get_video_info(url)
    return jsonify(info)

@app.route('/api/download', methods=['POST'])
def download():
    """비디오 및 썸네일 다운로드"""
    data = request.json
    url = data.get('url')
    is_playlist = data.get('is_playlist', False)
    download_all = data.get('download_all', False)
    
    if not url:
        return jsonify({'error': 'URL이 제공되지 않았습니다.'})
    
    # 임시 디렉토리 생성
    session_id = str(uuid.uuid4())
    session_dir = os.path.join(TEMP_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    try:
        if is_playlist and download_all:
            # 재생목록 전체 다운로드
            zip_filename = f"playlist_{int(time.time())}.zip"
            zip_path = os.path.join(session_dir, zip_filename)
            
            # 재생목록 정보 가져오기
            playlist_info = get_video_info(url)
            
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                # 각 비디오 다운로드 및 ZIP에 추가
                for i, video in enumerate(playlist_info.get('videos', [])):
                    if 'id' in video:
                        video_url = f"https://www.youtube.com/watch?v={video['id']}"
                        video_info = get_video_info(video_url)
                        
                        if 'error' not in video_info:
                            # 파일명 정리
                            safe_title = sanitize_filename(video.get('title', f"video_{i}"))
                            
                            # 비디오 다운로드
                            video_filename = f"{i+1:03d}_{safe_title}.mp4"
                            video_path = os.path.join(session_dir, video_filename)
                            download_video(video_url, video_path)
                            
                            # 썸네일 다운로드
                            if 'thumbnail_url' in video_info:
                                thumbnail_filename = f"{i+1:03d}_{safe_title}.jpg"
                                thumbnail_path = os.path.join(session_dir, thumbnail_filename)
                                download_thumbnail(video_info['thumbnail_url'], thumbnail_path)
                                
                                # ZIP에 추가
                                if os.path.exists(thumbnail_path):
                                    zipf.write(thumbnail_path, thumbnail_filename)
                            
                            # ZIP에 추가
                            if os.path.exists(video_path):
                                zipf.write(video_path, video_filename)
            
            # ZIP 파일 다운로드 URL 반환
            download_url = f"/download/{session_id}/{zip_filename}"
            return jsonify({
                'download_url': download_url
            })
            
        else:
            # 단일 비디오 다운로드
            info = get_video_info(url)
            
            if 'error' in info:
                return jsonify(info)
            
            if is_playlist and not download_all:
                # 재생목록의 첫 번째 비디오만 다운로드
                if len(info.get('videos', [])) > 0:
                    first_video = info['videos'][0]
                    url = f"https://www.youtube.com/watch?v={first_video['id']}"
                    safe_title = sanitize_filename(first_video.get('title', 'video'))
                    info = get_video_info(url)
                else:
                    return jsonify({'error': '재생목록에 비디오가 없습니다.'})
            else:
                safe_title = sanitize_filename(info.get('title', 'video'))
            
            # 비디오 파일 다운로드
            video_filename = f"{safe_title}.mp4"
            video_path = os.path.join(session_dir, video_filename)
            download_video(url, video_path)
            
            # 썸네일 다운로드
            thumbnail_filename = f"{safe_title}.jpg"
            thumbnail_path = os.path.join(session_dir, thumbnail_filename)
            download_thumbnail(info['thumbnail_url'], thumbnail_path)
            
            # 다운로드 URL 반환
            video_url = f"/download/{session_id}/{video_filename}"
            thumbnail_url = f"/download/{session_id}/{thumbnail_filename}"
            
            return jsonify({
                'video_url': video_url,
                'thumbnail_url': thumbnail_url,
                'video_filename': video_filename,
                'thumbnail_filename': thumbnail_filename
            })
            
    except Exception as e:
        return jsonify({'error': f'다운로드 중 오류가 발생했습니다: {str(e)}'})

@app.route('/download/<session_id>/<filename>')
def download_file(session_id, filename):
    """임시 디렉토리에서 파일 다운로드"""
    file_path = os.path.join(TEMP_DIR, session_id, secure_filename(filename))
    
    if not os.path.exists(file_path):
        return jsonify({'error': '파일을 찾을 수 없습니다.'}), 404
    
    # 파일 다운로드 후 삭제를 위한 콜백
    def remove_after_download(file_path):
        try:
            os.remove(file_path)
        except:
            pass
    
    # 파일 반환 및 다운로드 후 삭제 예약
    response = send_file(file_path, as_attachment=True)
    response.call_on_close(lambda: remove_after_download(file_path))
    return response

@app.route('/')
def index():
    """메인 페이지"""
    return app.send_static_file('index.html')

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)

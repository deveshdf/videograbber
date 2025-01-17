from flask import Flask, render_template, request, jsonify, send_file, Response
import yt_dlp
import os
import tempfile
import json
from urllib.parse import urlparse, parse_qs
import requests
import time
import random

app = Flask(__name__)

def get_video_id(url):
    """Extract video ID from YouTube URL"""
    parsed_url = urlparse(url)
    if parsed_url.hostname in ['www.youtube.com', 'youtube.com']:
        if parsed_url.path == '/watch':
            return parse_qs(parsed_url.query)['v'][0]
        elif parsed_url.path.startswith(('/shorts/', '/v/')):
            return parsed_url.path.split('/')[2]
    elif parsed_url.hostname == 'youtu.be':
        return parsed_url.path[1:]
    return None

def bypass_age_gate(url):
    """Bypass age gate by using an embed URL"""
    video_id = None
    parsed_url = urlparse(url)
    
    if parsed_url.hostname in ['www.youtube.com', 'youtube.com']:
        if parsed_url.path == '/watch':
            video_id = parse_qs(parsed_url.query)['v'][0]
        elif parsed_url.path.startswith(('/shorts/', '/v/')):
            video_id = parsed_url.path.split('/')[2]
    elif parsed_url.hostname == 'youtu.be':
        video_id = parsed_url.path[1:]
        
    if not video_id:
        return url
        
    return f'https://www.youtube.com/embed/{video_id}'

def get_youtube_info(url):
    """Get video information using yt-dlp"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'best',
        'extract_flat': True,
        'no_check_certificates': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    }
    
    # Define the exact formats we want to use
    VIDEO_FORMATS = {
        1080: '137',  # 1080p video only
        720: '136',   # 720p video only
        480: '135',   # 480p video only
        360: '134',   # 360p video only
        240: '133',   # 240p video only
        144: '160'    # 144p video only
    }
    AUDIO_FORMAT = '140'  # m4a audio
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            available_formats = {f['format_id']: f for f in info['formats']}
            
            streams = {
                'hd': [],
                'sd': [],
                'audio': []
            }
            
            # Add audio format
            if AUDIO_FORMAT in available_formats:
                streams['audio'].append({
                    'format_id': f"{AUDIO_FORMAT}",  # Audio only
                    'ext': 'mp3',
                    'type': 'audio',
                    'quality': 128,
                    'quality_label': 'MP3 Audio'
                })
            
            # Add video formats with audio
            for height, video_format in VIDEO_FORMATS.items():
                if video_format in available_formats:
                    format_id = f"{video_format}+{AUDIO_FORMAT}"  # Combine video with audio
                    stream_info = {
                        'format_id': format_id,
                        'ext': 'mp4',
                        'type': 'video',
                        'quality': height,
                        'quality_label': f"{height}p"
                    }
                    
                    if height >= 720:
                        streams['hd'].append(stream_info)
                    else:
                        streams['sd'].append(stream_info)
            
            # Sort streams by quality
            for key in streams:
                streams[key].sort(key=lambda x: x['quality'], reverse=True)
            
            return {
                'title': info['title'],
                'thumbnail': info['thumbnail'],
                'duration': info['duration'],
                'author': info['uploader'],
                'description': info.get('description', '')[:200] + '...' if info.get('description') else '',
                'streams': streams
            }
        except Exception as e:
            raise Exception(f"Error extracting video info: {str(e)}")

def get_instagram_info(url):
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            return {
                'title': info.get('title', 'Instagram Video'),
                'thumbnail': info.get('thumbnail', ''),
                'author': info.get('uploader', ''),
                'duration': info.get('duration', 'N/A'),
                'description': info.get('description', ''),
                'formats': [{
                    'format_id': 'instagram_video',
                    'ext': 'mp4',
                    'format': 'Instagram Video',
                    'filesize': -1,
                    'resolution': 'Original Quality'
                }]
            }
    except Exception as e:
        raise Exception(f'Failed to get Instagram info: {str(e)}')

def download_youtube(url, format_id):
    try:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tmp') as tmp_file:
            temp_path = tmp_file.name
        
        # Check if this is an audio download
        is_audio = format_id == '140'
        
        # Set FFmpeg paths
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ffmpeg_dir = os.path.join(current_dir, 'ffmpeg')
        
        if is_audio:
            # For audio, download as m4a first
            ydl_opts = {
                'format': 'bestaudio[ext=m4a]',
                'outtmpl': temp_path + '.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'ffmpeg_location': ffmpeg_dir,
                'postprocessors': [],  # No post-processing for now
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
            }
        else:
            # For video, use original settings
            ydl_opts = {
                'format': format_id,
                'outtmpl': temp_path,
                'quiet': True,
                'no_warnings': True,
                'ffmpeg_location': ffmpeg_dir,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
            }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # Extract info first
                info = ydl.extract_info(url, download=False)
                
                # Download the file
                ydl.download([url])
                
                # Get the actual downloaded file path
                if is_audio:
                    downloaded_file = temp_path + '.m4a'
                    output_filename = "".join(c for c in info['title'] if c.isalnum() or c in (' ', '-', '_')).rstrip() + '.m4a'
                    mime_type = 'audio/mp4'
                else:
                    downloaded_file = temp_path + '.mp4'
                    output_filename = "".join(c for c in info['title'] if c.isalnum() or c in (' ', '-', '_')).rstrip() + '.mp4'
                    mime_type = 'video/mp4'
                
                if not os.path.exists(downloaded_file):
                    return jsonify({'error': 'Failed to download'})
                
                # Stream the file
                def generate():
                    try:
                        with open(downloaded_file, 'rb') as f:
                            while True:
                                chunk = f.read(8192)
                                if not chunk:
                                    break
                                yield chunk
                    finally:
                        # Clean up temp file
                        if os.path.exists(downloaded_file):
                            os.unlink(downloaded_file)
                
                response = Response(generate(), mimetype=mime_type)
                response.headers['Content-Disposition'] = f'attachment; filename="{output_filename}"'
                return response
                
            except Exception as download_error:
                if 'downloaded_file' in locals() and os.path.exists(downloaded_file):
                    os.unlink(downloaded_file)
                return jsonify({'error': f'Download error: {str(download_error)}'})
                
    except Exception as e:
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.unlink(temp_path)
        return jsonify({'error': f'YouTube download error: {str(e)}'})

def download_instagram(url):
    try:
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, 'video.mp4')
        
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'outtmpl': temp_path,
                'format': 'best'
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            if not os.path.exists(temp_path):
                raise Exception('Video file not found after download')
            
            # Get filename from URL
            filename = f"instagram_video_{int(time.time())}.mp4"
            
            return send_file(
                temp_path,
                as_attachment=True,
                download_name=filename,
                mimetype='video/mp4'
            )
        finally:
            # Clean up temporary directory
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    except Exception as e:
        return jsonify({'error': f'Instagram download error: {str(e)}'})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/how-to-use')
def how_to_use():
    return render_template('how-to-use.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy-policy.html')

@app.route('/disclaimer')
def disclaimer():
    return render_template('disclaimer.html')

@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms-of-service.html')

@app.route('/get-video-info', methods=['POST'])
def get_video_info():
    url = request.form.get('url')
    platform = request.form.get('platform')

    try:
        if platform == 'youtube':
            video_id = get_video_id(url)
            if not video_id:
                return jsonify({'error': 'Invalid YouTube URL'}), 400
            
            info = get_youtube_info(url)
            return jsonify(info)
        elif platform == 'instagram':
            info = get_instagram_info(url)
            return jsonify(info)
        else:
            return jsonify({'error': 'Unsupported platform'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url')
    platform = request.form.get('platform')
    format_id = request.form.get('format_id')

    try:
        if platform == 'youtube':
            return download_youtube(url, format_id)
        elif platform == 'instagram':
            return download_instagram(url)
        else:
            return jsonify({'error': 'Invalid platform selected'})
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)

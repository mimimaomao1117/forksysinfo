"""Build the English evidence walkthrough from genuine captures and narration.

Requires Python 3, Pillow, ffmpeg and ffprobe. First generate speech_NN.wav
with narrate_video.ps1 on Windows, or provide the same English cue recordings.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PROJECT = Path(__file__).resolve().parents[1]
MEDIA = PROJECT / 'media'
WIDTH, HEIGHT = 1920, 1080


def run(args):
    result = subprocess.run([str(x) for x in args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-5000:])
    return result.stdout


def stamp(seconds):
    value = round(seconds * 1000)
    return f'{value//3600000:02}:{value//60000%60:02}:{value//1000%60:02},{value%1000:03}'


def wrap(text, font, maximum):
    lines, line = [], ''
    for word in text.split():
        candidate = (line + ' ' + word).strip()
        if line and font.getlength(candidate) > maximum:
            lines.append(line)
            line = word
        else:
            line = candidate
    return lines + [line]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--ffmpeg', default=shutil.which('ffmpeg') or 'ffmpeg')
    parser.add_argument('--ffprobe', default=shutil.which('ffprobe') or 'ffprobe')
    parser.add_argument('--font', default='C:/Windows/Fonts/arial.ttf')
    parser.add_argument('--bold-font', default='C:/Windows/Fonts/arialbd.ttf')
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    timeline = json.loads((MEDIA / 'video_timeline.json').read_text(encoding='utf-8'))
    assert sum(ch['duration'] for ch in timeline['chapters']) == 120

    def font(size, bold=False):
        return ImageFont.truetype(args.bold_font if bold else args.font, size)

    cues, transcript, elapsed = [], [timeline['title'], 'English narration transcript',
        'Narrated walkthrough of the report figures and recorded Linux command-line evidence.',
        'Sources: media/cli/, media/diagrams/, evidence-cli/.', ''], 0.0
    for chapter in timeline['chapters']:
        assert abs(sum(c['duration'] for c in chapter['cues']) - chapter['duration']) < 0.001
        transcript += [f'{int(elapsed)//60:02}:{int(elapsed)%60:02}  {chapter["title"]}']
        for cue in chapter['cues']:
            cue = dict(cue, start=elapsed, chapter=chapter['title'], source=chapter['source'])
            cues.append(cue)
            transcript.append(cue['text'])
            elapsed += cue['duration']
        transcript.append('')
    assert abs(elapsed - 120) < 0.001
    (MEDIA / 'ForkSysInfo_2min_transcript.txt').write_text('\n'.join(transcript), encoding='utf-8')

    playlist, subtitles, audit = [], [], []
    audio_parts = []
    source_hashes = {}
    for i, cue in enumerate(cues):
        image_path = MEDIA / cue['source']
        source_hashes[cue['source']] = hashlib.sha256(image_path.read_bytes()).hexdigest()
        with Image.open(image_path) as source:
            image = source.convert('RGB')
        crop = cue.get('crop')
        if crop is None and cue['source'].startswith('cli/'):
            # Discard only blank console rows; all recorded output is preserved.
            box = image.getbbox()
            crop = [0, 0, image.width, min(image.height, box[3] + 18)]
        if crop:
            image = image.crop(tuple(crop))
        ratio = min(1800 / image.width, 790 / image.height)
        image = image.resize((round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS)
        frame = Image.new('RGB', (WIDTH, HEIGHT), 'white')
        draw = ImageDraw.Draw(frame)
        heading = font(38, True)
        while heading.getlength(cue['chapter']) > 1790:
            heading = font(heading.size - 1, True)
        draw.text((60, 27), cue['chapter'], fill='#111111', font=heading)
        label = 'Recorded Linux console' if cue['source'].startswith('cli/') else 'Report diagram'
        if cue.get('crop'):
            label += ' (detail)'
        draw.text((60, 83), f'{label}  |  media/{cue["source"]}', fill='#555555', font=font(22))
        frame.paste(image, ((WIDTH - image.width)//2, 130 + (790-image.height)//2))
        draw.line((60, 940, 1860, 940), fill='#bbbbbb', width=1)
        caption = wrap(cue['text'], font(37), 1770)
        assert len(caption) <= 2, cue['text']
        top = 967 if len(caption) == 1 else 952
        for row, line in enumerate(caption):
            draw.text((960, top + row*48), line, fill='#111111', font=font(37), anchor='mt')
        frame_path = args.work / f'frame_{i:02}.png'
        frame.save(frame_path)
        playlist += [f"file '{frame_path.resolve().as_posix()}'", f'duration {cue["duration"]:.3f}']
        subtitles += [str(i+1), f'{stamp(cue["start"])} --> {stamp(cue["start"]+cue["duration"])}', '\n'.join(caption), '']

        speech_path = args.work / f'speech_{i:02}.wav'
        with wave.open(str(speech_path), 'rb') as speech:
            speech_seconds = speech.getnframes() / speech.getframerate()
        # Keep the original pace unless a cue needs a modest increase to fit.
        speed = max(1.0, speech_seconds / (cue['duration'] - 0.32))
        assert speed < 1.32, (i, speed, 'Shorten this cue before rendering.')
        audio_path = args.work / f'audio_{i:02}.wav'
        run([args.ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-i', speech_path,
             '-af', f'atempo={speed:.8f},loudnorm=I=-18:TP=-1.5:LRA=9,aresample=48000,adelay=120,apad,atrim=duration={cue["duration"]}',
             '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s16le', audio_path])
        # Filter latency can leave a WAV slightly shorter than its requested
        # trim duration. Pad each cue to its exact sample count so subsequent
        # narration stays aligned with the captions throughout the video.
        with wave.open(str(audio_path), 'rb') as audio:
            samples = audio.readframes(audio.getnframes())
        expected_bytes = round(cue['duration'] * 48000) * 2
        assert len(samples) <= expected_bytes
        assert expected_bytes - len(samples) < 48000, (i, 'Unexpected audio shortfall')
        with wave.open(str(audio_path), 'wb') as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(48000)
            audio.writeframes(samples + bytes(expected_bytes-len(samples)))
        audio_parts.append(audio_path)
        audit.append({'start': cue['start'], 'duration': cue['duration'], 'source': cue['source'],
                      'crop': crop, 'caption': cue['text'], 'speech_seconds': round(speech_seconds, 3),
                      'tempo_factor': round(speed, 4)})

    playlist.append(f"file '{frame_path.resolve().as_posix()}'")
    (args.work / 'frames.txt').write_text('\n'.join(playlist) + '\n', encoding='utf-8')
    (MEDIA / 'ForkSysInfo_2min.en.srt').write_text('\n'.join(subtitles), encoding='utf-8')
    with wave.open(str(args.work / 'narration_120.wav'), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(48000)
        for path in audio_parts:
            with wave.open(str(path), 'rb') as audio:
                output.writeframes(audio.readframes(audio.getnframes()))

    destination = MEDIA / 'ForkSysInfo_2min.mp4'
    run([args.ffmpeg, '-hide_banner', '-loglevel', 'warning', '-y',
         '-f', 'concat', '-safe', '0', '-i', args.work / 'frames.txt',
         '-i', args.work / 'narration_120.wav', '-map', '0:v:0', '-map', '1:a:0',
         '-vf', 'fps=25,format=yuv420p', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
         '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-t', '120', '-movflags', '+faststart',
         '-metadata', 'title=ForkSysInfo: English Demonstration',
         '-metadata', 'comment=English narrated walkthrough of native Linux CLI evidence and report diagrams.',
         '-metadata:s:a:0', 'language=eng', '-metadata:s:v:0', 'language=eng', destination])
    info = json.loads(run([args.ffprobe, '-v', 'error', '-show_entries',
        'format=duration,size:stream=codec_name,width,height,duration,sample_rate,channels:stream_tags=language',
        '-of', 'json', destination]))
    assert abs(float(info['format']['duration']) - 120) < .05
    assert all(abs(float(s['duration']) - 120) < .05 for s in info['streams'])
    manifest = {'language': 'en-US', 'duration_seconds': 120, 'voice': timeline['voice'],
                'narration_method': 'Windows System.Speech synthetic English narration',
                'visual_method': 'Original report diagrams and native console captures, with labelled crops and English captions',
                'media': info, 'sources_sha256': source_hashes, 'cues': audit,
                'video_sha256': hashlib.sha256(destination.read_bytes()).hexdigest()}
    (MEDIA / 'video_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'video': str(destination), 'media': info, 'cues': len(cues),
                      'maximum_tempo': max(x['tempo_factor'] for x in audit)}, indent=2))


if __name__ == '__main__':
    main()

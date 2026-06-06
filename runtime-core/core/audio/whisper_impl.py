try:
    import whisper
except ImportError:
    whisper = None
import logging
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

_MODEL_CACHE: Dict[Tuple[str, str], Any] = {}


def _get_whisper_model(model_type: str, device: str):
    if whisper is None:
        raise ImportError('Whisper module not available')
    cache_key = (model_type, device)
    if cache_key not in _MODEL_CACHE:
        logger.info('Loading openai-whisper model=%s device=%s', model_type, device)
        _MODEL_CACHE[cache_key] = whisper.load_model(model_type, device=device)
    return _MODEL_CACHE[cache_key]


def transcribe_audio_whisper(segments, type='base', device='cpu', language='zh', task='transcribe'):
    import os
    import time

    os.environ['OMP_NUM_THREADS'] = '1'
    start = time.time()
    model = _get_whisper_model(type, device)

    results = []
    for segment_path in segments:
        options = {'verbose': False, 'task': task}
        if language:
            options['language'] = language
        result = model.transcribe(segment_path, **options)
        results.append((result.get('text') or '').strip())

    logger.info('audio to txt cost %s', time.time() - start)
    return results


def transcribe_audio_details(filepath, model_type='base', device='cpu', language='zh', task='transcribe'):
    if whisper is None:
        raise ImportError('Whisper module not available')

    model = _get_whisper_model(model_type, device)
    options = {'verbose': False, 'task': task}
    if language:
        options['language'] = language

    result = model.transcribe(filepath, **options)
    text = (result.get('text') or '').strip()
    detected_language = result.get('language') or language or 'zh'
    segments = [
        {
            'start': seg.get('start'),
            'end': seg.get('end'),
            'text': (seg.get('text') or '').strip(),
        }
        for seg in (result.get('segments') or [])
    ]
    logger.info('Detected language: %s, chars: %s, segments: %s', detected_language, len(text), len(segments))
    return {
        'text': text,
        'language': detected_language,
        'segments': segments,
        'duration': result.get('duration'),
    }


def transcribe_audio(filepath, model_type='base', device='cpu', language='zh', task='transcribe'):
    payload = transcribe_audio_details(
        filepath,
        model_type=model_type,
        device=device,
        language=language,
        task=task,
    )
    return payload['text'], payload['language']


def _transcribe_audio(segments: list[str], model=None) -> str:
    try:
        result = ''
        for segment in segments:
            audio_transcript = model.speech_to_text(segment)
            result += audio_transcript
        return result
    except Exception:
        parts = transcribe_audio_whisper(segments=segments)
        if isinstance(parts, list):
            return ''.join(parts)
        return str(parts)

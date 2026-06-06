"""Faster-Whisper STT backend with process-level model cache."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None  # type: ignore[misc, assignment]

_MODEL_CACHE: Dict[Tuple[str, str, str], Any] = {}


def faster_whisper_available() -> bool:
    return WhisperModel is not None


def _resolve_compute_type(device: str, compute_type: Optional[str]) -> str:
    if compute_type:
        return compute_type
    env_value = os.environ.get('WHISPER_COMPUTE_TYPE', '').strip()
    if env_value:
        return env_value
    return 'float16' if device == 'cuda' else 'int8'


def _get_model(model_type: str, device: str, compute_type: Optional[str]) -> Any:
    if WhisperModel is None:
        raise ImportError('faster-whisper is not installed')

    resolved_compute = _resolve_compute_type(device, compute_type)
    cache_key = (model_type, device, resolved_compute)
    if cache_key not in _MODEL_CACHE:
        logger.info(
            'Loading faster-whisper model=%s device=%s compute_type=%s',
            model_type,
            device,
            resolved_compute,
        )
        _MODEL_CACHE[cache_key] = WhisperModel(
            model_type,
            device=device,
            compute_type=resolved_compute,
        )
    return _MODEL_CACHE[cache_key]


def transcribe_audio_details(
    filepath: str,
    model_type: str = 'base',
    device: str = 'cpu',
    language: str = 'zh',
    task: str = 'transcribe',
    compute_type: Optional[str] = None,
) -> Dict[str, Any]:
    model = _get_model(model_type, device, compute_type)
    transcribe_kwargs: Dict[str, Any] = {'task': task}
    if language:
        transcribe_kwargs['language'] = language

    segments_iter, info = model.transcribe(filepath, **transcribe_kwargs)
    segments = [
        {
            'start': segment.start,
            'end': segment.end,
            'text': (segment.text or '').strip(),
        }
        for segment in segments_iter
    ]
    text = ''.join(segment['text'] for segment in segments).strip()
    detected_language = getattr(info, 'language', None) or language or 'zh'
    duration = getattr(info, 'duration', None)

    logger.info(
        'faster-whisper language=%s chars=%s segments=%s duration=%s',
        detected_language,
        len(text),
        len(segments),
        duration,
    )
    return {
        'text': text,
        'language': detected_language,
        'segments': segments,
        'duration': duration,
    }

from celery import Celery
from storage.models import db, Video
from core.videos.summarize_youtube_video import summarize_youtube_video
# Removed legacy import: from agents.analyzer_legacy.summarize import summarize_openai

def mcp_summarize(transcriptions, system_prompt=None, output_file=None):
    from core.mcp_gateway import get_mcp_gateway
    import asyncio
    
    async def _call():
        gateway = get_mcp_gateway()
        text_content = "\\n".join(transcriptions) if isinstance(transcriptions, list) else str(transcriptions)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": f"Please summarize the following: {text_content}"})
        
        try:
            resp = await gateway.call("ai_mcp", "chat_analyze", {"messages": messages})
            if isinstance(resp, dict) and 'response' in resp:
                return resp['response']
            return str(resp)
        except Exception as e:
            return f"Summary failed: {e}"
            
    res = asyncio.run(_call())
    if output_file:
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(res)
        except Exception:
            pass
    return [res]

celery = Celery(__name__, broker='redis://localhost:6379/0')

@celery.task
def process_video(video_id):
    with db.session.no_autoflush:
        video = Video.query.filter_by(video_id=video_id).first()
    if video:
        youtube_url = video.video_url
        outputs_dir = "outputs/"
        long_summary, short_summary = summarize_youtube_video(youtube_url, outputs_dir, None, None, mcp_summarize)
        video.status = 'completed'
        video.summary = long_summary
        db.session.commit()
        return {"message": "Video processed"}
    return {"message": "Video not found"}
import streamlit as st
import requests
from mcp_legacy.servers.youtube.youtube_subscribe_list import get_subscribe_list
from summarize_youtube_video import summarize_youtube_video, summarize_openai

def get_subscriptions():
    try:
        response = requests.get("http://127.0.0.1:5050/subscriptions")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Failed to fetch subscriptions: {e}")
        st.warning("Please check the URL's validity or try again later.")
        return []

def get_videos(channel_id):
    try:
        response = requests.get(f"http://127.0.0.1:5050/videos/{channel_id}")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Failed to fetch videos: {e}")
        st.warning("Please check the URL's validity or try again later.")
        return []

def save_subscriptions(subscription_list):
    for subscription in subscription_list:
        channel_id = subscription['channel']['channel_id']
        channel_title = subscription['channel']['channel_title']
        try:
            response = requests.post("http://127.0.0.1:5050/subscriptions", json={"channel_id": channel_id, "channel_title": channel_title})
            response.raise_for_status()
        except requests.RequestException as e:
            st.error(f"Failed to save subscription {channel_id}: {e}")
            st.warning("Please check the URL's validity or try again later.")

def save_videos(channel_id, video_list):
    for video in video_list:
        video_id = video['video_id']
        video_title = video['video_title']
        video_url = video['video_url']
        published_at = video['published_at']
        try:
            response = requests.post(f"http://127.0.0.1:5050/videos/{channel_id}", json={
                "video_id": video_id,
                "video_title": video_title,
                "video_url": video_url,
                "published_at": published_at
            })
            response.raise_for_status()
        except requests.RequestException as e:
            st.error(f"Failed to save video {video_id}: {e}")
            st.warning("Please check the URL's validity or try again later.")

def update_video_status(video_id, status, summary=None, short_summary=None):
    data = {"status": status}
    if summary:
        data["summary"] = summary,
        data["short_summary"] = short_summary
    try:
        response = requests.patch(f"http://127.0.0.1:500/videos/{video_id}", json=data)
        response.raise_for_status()
    except requests.RequestException as e:
        st.error(f"Failed to update video status {video_id}: {e}")
        st.warning("Please check the URL's validity or try again later.")

def do_update_subscriptions():
    subscription_list = get_subscribe_list(last_n_days=3)
    save_subscriptions(subscription_list)
    subscriptions = get_subscriptions()
    return subscriptions

def main():
    st.title("YouGPTube Summarizer")
    use_subscription = st.sidebar.checkbox("Use YouTube Subscription List")
    update_now = st.sidebar.checkbox("Update Youtube Subscription Now")

    if use_subscription:
        if not update_now:
            subscriptions = get_subscriptions()
            if not subscriptions:
                subscriptions = do_update_subscriptions()
        else:
            subscriptions = do_update_subscriptions()
        
        channel_titles = [sub['channel_title'] for sub in subscriptions]
        selected_channel_title = st.sidebar.selectbox("Select Channel:", channel_titles)
        selected_channel_id = next(sub['channel_id'] for sub in subscriptions if sub['channel_title'] == selected_channel_title)

        videos = get_videos(selected_channel_id)
        if not videos:
            subscription_list = get_subscribe_list(last_n_days=3)
            selected_channel = next((channel for channel in subscription_list if channel['channel']['channel_title'] == selected_channel_title), None)
            if selected_channel:
                video_list = selected_channel['latest_videos']
                save_videos(selected_channel_id, video_list)
                videos = get_videos(selected_channel_id)

        video_titles = [video['video_title'] for video in videos]
        selected_video_title = st.sidebar.selectbox("Select Video:", video_titles)
        selected_video = next(video for video in videos if video['video_title'] == selected_video_title)

        if selected_video['status'] == 'unprocessed':
            youtube_url = selected_video['video_url']
            try:
                long_summary, short_summary = summarize_youtube_video(youtube_url, "outputs/", st.progress(0), st.empty(), summarize_openai)
                update_video_status(selected_video['video_id'], 'completed', summary=long_summary, short_summary=short_summary)
            except Exception as e:
                st.error(f"Error processing video: {e}")
        else:
            st.write("Summary:")
            st.write(selected_video['summary'])

if __name__ == "__main__":
    main()
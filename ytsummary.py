import os
import tempfile
import argparse
import shutil
import glob
from openai import OpenAI
from googleapiclient.discovery import build
import yt_dlp
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

def get_channel_id_from_handle(youtube, channel_handle):
    """
    Converts a YouTube channel handle to its channel ID.
    
    Args:
        youtube: The authenticated YouTube Data API service object.
        channel_handle (str): The handle of the YouTube channel (with or without @ symbol).

    Returns:
        str: The channel ID if found, None otherwise.
    """
    try:
        # Clean the handle - remove @ if present and ensure it starts with @
        clean_handle = channel_handle.strip()
        if not clean_handle.startswith('@'):
            clean_handle = '@' + clean_handle
        
        # Try to get channel by handle using the newer forHandle parameter
        try:
            channel_request = youtube.channels().list(
                part='id',
                forHandle=clean_handle
            )
            channel_response = channel_request.execute()
            
            if channel_response['items']:
                return channel_response['items'][0]['id']
        except Exception as e:
            print(f"⚠️  forHandle API not available or failed for '{clean_handle}': {e}")
        
        # Fallback: try without @ symbol as username
        handle_without_at = clean_handle[1:]  # Remove the @ symbol
        try:
            channel_request = youtube.channels().list(
                part='id',
                forUsername=handle_without_at
            )
            channel_response = channel_request.execute()
            
            if channel_response['items']:
                return channel_response['items'][0]['id']
        except:
            pass  # If forUsername fails, continue to search method
        
        # If handle lookup fails, search for the channel using the handle
        search_request = youtube.search().list(
            part='snippet',
            q=clean_handle,
            type='channel',
            maxResults=10
        )
        search_response = search_request.execute()
        
        # Look for exact or close matches in custom URL or handle
        for item in search_response['items']:
            # Check if the channel title or custom URL matches
            if (clean_handle.lower() in item['snippet']['title'].lower() or 
                handle_without_at.lower() in item['snippet']['title'].lower()):
                return item['snippet']['channelId']
        
        # If no exact match, return the first result if available
        if search_response['items']:
            print(f"⚠️  No exact match found for handle '{clean_handle}'. Using closest match: '{search_response['items'][0]['snippet']['title']}'")
            return search_response['items'][0]['snippet']['channelId']
        
        print(f"❌ No channel found for handle: {clean_handle}")
        return None
        
    except Exception as e:
        print(f"An error occurred while searching for channel handle '{channel_handle}': {e}")
        return None

def get_channel_videos(youtube, channel_id, cutoff_date):
    """
    Fetches videos from a specific YouTube channel published after a cutoff date.
    Excludes live streams and previously recorded live sessions.
    
    Args:
        youtube: The authenticated YouTube Data API service object.
        channel_id (str): The ID of the YouTube channel.
        cutoff_date (datetime): The earliest publish date for videos to fetch.

    Returns:
        list: A list of dictionaries, where each dictionary contains a video's details.
    """
    try:
        # Get the channel's 'uploads' playlist ID
        channel_request = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        )
        channel_response = channel_request.execute()
        playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        # Get the videos from the 'uploads' playlist
        videos = []
        next_page_token = None
        while True:
            playlist_request = youtube.playlistItems().list(
                playlistId=playlist_id,
                part='snippet',
                maxResults=50, # Max allowed value
                pageToken=next_page_token
            )
            playlist_response = playlist_request.execute()

            # Collect video IDs to batch fetch their details
            video_ids_batch = []
            video_items_map = {}
            
            for item in playlist_response['items']:
                video_published_at_str = item['snippet']['publishedAt']
                # Parse the ISO 8601 date string
                video_published_at = datetime.fromisoformat(video_published_at_str.replace('Z', '+00:00'))

                if video_published_at >= cutoff_date:
                    video_id = item['snippet']['resourceId']['videoId']
                    video_ids_batch.append(video_id)
                    video_items_map[video_id] = {
                        'id': video_id,
                        'title': item['snippet']['title'],
                        'published_at': video_published_at
                    }
                else:
                    # Videos are sorted by date, so we can stop once we pass the cutoff
                    break
            
            # Batch fetch video details to check for live streaming
            if video_ids_batch:
                video_details_request = youtube.videos().list(
                    part='liveStreamingDetails',
                    id=','.join(video_ids_batch)
                )
                video_details_response = video_details_request.execute()
                
                # Filter out live content
                for video_detail in video_details_response['items']:
                    video_id = video_detail['id']
                    is_live_content = 'liveStreamingDetails' in video_detail
                    
                    if not is_live_content:
                        # Only add non-live content
                        video_items_map[video_id]['is_live_content'] = False
                        video_items_map[video_id]['channel_id'] = channel_id
                        videos.append(video_items_map[video_id])
                    else:
                        print(f"🔴 Skipping live content: {video_items_map[video_id]['title']}")
            
            # Check if we hit the cutoff date
            if len(video_ids_batch) == 0:
                break
            
            next_page_token = playlist_response.get('nextPageToken')
            if not next_page_token:
                break
        return videos
    except Exception as e:
        print(f"An error occurred fetching videos for channel {channel_id}: {e}")
        return []

def get_transcript(video_id):
    """
    Retrieves the full text transcript for a given YouTube video ID using yt-dlp.

    Args:
        video_id (str): The unique ID of the YouTube video.

    Returns:
        str: The full transcript as a single string, or None if not available.
    """
    try:
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Configure yt-dlp options
        ydl_opts = {
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en'],
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            ydl_opts['outtmpl'] = os.path.join(temp_dir, '%(id)s.%(ext)s')
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info and download subtitles
                info = ydl.extract_info(video_url, download=False)
                ydl.download([video_url])
                
                # Look for subtitle files
                subtitle_files = []
                for file in os.listdir(temp_dir):
                    if file.endswith('.vtt') and video_id in file:
                        subtitle_files.append(os.path.join(temp_dir, file))
                
                if not subtitle_files:
                    print(f"No subtitle files found for video ID: {video_id}")
                    return None
                
                # Read the first available subtitle file
                subtitle_file = subtitle_files[0]
                with open(subtitle_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Parse VTT content to extract text
                transcript_text = []
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    # Skip VTT headers, timestamps, and empty lines
                    if (line and 
                        not line.startswith('WEBVTT') and 
                        not line.startswith('NOTE') and
                        not '-->' in line and
                        not line.isdigit()):
                        # Remove VTT formatting tags
                        clean_line = line.replace('<c>', '').replace('</c>', '')
                        clean_line = clean_line.replace('<i>', '').replace('</i>', '')
                        clean_line = clean_line.replace('<b>', '').replace('</b>', '')
                        if clean_line:
                            transcript_text.append(clean_line)
                
                return ' '.join(transcript_text)
                
    except Exception as e:
        print(f"An error occurred retrieving transcript for video ID {video_id}: {e}")
        return None

def get_channel_handle_from_id(youtube, channel_id):
    """
    Gets the channel handle from a channel ID.
    
    Args:
        youtube: The authenticated YouTube Data API service object.
        channel_id (str): The ID of the YouTube channel.

    Returns:
        str: The channel handle (with @ symbol) if found, None otherwise.
    """
    try:
        channel_request = youtube.channels().list(
            part='snippet',
            id=channel_id
        )
        channel_response = channel_request.execute()
        
        if channel_response['items']:
            channel_info = channel_response['items'][0]['snippet']
            
            # Try to get the custom URL which often contains the handle
            if 'customUrl' in channel_info:
                custom_url = channel_info['customUrl']
                # Custom URL might be in format @handle or just handle
                if custom_url.startswith('@'):
                    return custom_url
                else:
                    return f"@{custom_url}"
            
            # If no custom URL, return the channel title as fallback
            return f"@{channel_info['title']}"
        
        return None
        
    except Exception as e:
        print(f"An error occurred getting channel handle for ID {channel_id}: {e}")
        return None

def get_video_details(youtube, video_id):
    """
    Fetches video details for a specific YouTube video ID.
    
    Args:
        youtube: The authenticated YouTube Data API service object.
        video_id (str): The ID of the YouTube video.

    Returns:
        dict: A dictionary containing video details, or None if not found.
    """
    try:
        video_request = youtube.videos().list(
            part='snippet,liveStreamingDetails',
            id=video_id
        )
        video_response = video_request.execute()
        
        if video_response['items']:
            item = video_response['items'][0]
            video_published_at_str = item['snippet']['publishedAt']
            # Parse the ISO 8601 date string
            video_published_at = datetime.fromisoformat(video_published_at_str.replace('Z', '+00:00'))
            
            # Check if this is a live stream (past or present)
            is_live_content = 'liveStreamingDetails' in item
            
            return {
                'id': video_id,
                'title': item['snippet']['title'],
                'published_at': video_published_at,
                'is_live_content': is_live_content,
                'channel_id': item['snippet']['channelId'],
                'channel_title': item['snippet']['channelTitle']
            }
        else:
            print(f"❌ No video found for ID: {video_id}")
            return None
            
    except Exception as e:
        print(f"An error occurred fetching video details for {video_id}: {e}")
        return None

def summarize_with_openrouter(api_key, transcript, prompt_file='prompt.txt', model='qwen/qwen3-30b-a3b-instruct-2507'):
    """
    Summarizes a given text using OpenRouter API.

    Args:
        api_key (str): Your OpenRouter API key.
        transcript (str): The text to be summarized.
        prompt_file (str): Path to the prompt file for AI summarization.
        model (str): The model to use for summarization.

    Returns:
        str: The generated summary, or an error message.
    """
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        
        # Read prompt from external file
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_template = f.read().strip()
        except FileNotFoundError:
            return f"Error: {prompt_file} file not found. Please ensure the prompt file exists in the project directory."
        except Exception as e:
            return f"Error reading {prompt_file}: {e}"
        
        prompt = f"{prompt_template}\n\n---\n\n{transcript}"
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000,
            temperature=0.3
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"An error occurred during summarization: {e}"

def create_datetime_folder():
    """
    Creates a datetime folder with format MMDDYY_HHMM inside the processed/ directory.
    If duplicate exists, increments with underscore and number.
    
    Returns:
        str: Path to the created datetime folder
    """
    now = datetime.now()
    base_folder_name = now.strftime("%m%d%y_%H%M")
    
    # Ensure processed directory exists
    processed_dir = "processed"
    os.makedirs(processed_dir, exist_ok=True)
    
    # Check for duplicates and increment if necessary
    counter = 0
    folder_name = os.path.join(processed_dir, base_folder_name)
    
    while os.path.exists(folder_name):
        counter += 1
        folder_name = os.path.join(processed_dir, f"{base_folder_name}_{counter}")
    
    # Create the datetime folder and subfolders
    os.makedirs(folder_name, exist_ok=True)
    transcripts_folder = os.path.join(folder_name, "transcripts")
    summaries_folder = os.path.join(folder_name, "summaries")
    os.makedirs(transcripts_folder, exist_ok=True)
    os.makedirs(summaries_folder, exist_ok=True)
    
    print(f"📁 Created datetime folder: {folder_name}")
    return folder_name

def find_existing_transcript(video_id, current_datetime_folder):
    """
    Searches for existing transcript files in other datetime folders within the processed/ directory.
    
    Args:
        video_id (str): The video ID to search for
        current_datetime_folder (str): The current datetime folder to exclude from search
    
    Returns:
        tuple: (transcript_path, summary_path) if found, (None, None) otherwise
    """
    processed_dir = "processed"
    
    # Check if processed directory exists
    if not os.path.exists(processed_dir):
        return None, None
    
    # Get all datetime folders (format: MMDDYY_HHMM or MMDDYY_HHMM_N) within processed/
    datetime_folders = []
    for item in os.listdir(processed_dir):
        item_path = os.path.join(processed_dir, item)
        if os.path.isdir(item_path) and item_path != current_datetime_folder:
            # Check if it matches datetime pattern
            parts = item.split('_')
            if len(parts) >= 2:
                date_part = parts[0]
                time_part = parts[1]
                if (len(date_part) == 6 and date_part.isdigit() and 
                    len(time_part) == 4 and time_part.isdigit()):
                    datetime_folders.append(item_path)
    
    # Search for transcript and summary files
    for folder in datetime_folders:
        transcript_path = os.path.join(folder, "transcripts", f"{video_id}_transcript.txt")
        summary_path = os.path.join(folder, "summaries", f"{video_id}_summary.md")
        
        if os.path.exists(transcript_path):
            summary_exists = os.path.exists(summary_path)
            return transcript_path, summary_path if summary_exists else None
    
    return None, None

def main():
    """
    Main function to orchestrate fetching, transcribing, and summarizing videos.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='YouTube Video Summarizer - Summarize videos from channel handles or specific video IDs',
        epilog='Example channel handle URL: https://www.youtube.com/@meetandrew'
    )
    parser.add_argument('inputs', nargs='+', help='Comma-separated YouTube channel handles (e.g., "@meetandrew,@codingwithdrew") or video IDs')
    parser.add_argument('--days', '-d', type=int, default=1, help='Number of days to look back for videos (default: 1)')
    parser.add_argument('--video-ids', '-v', action='store_true', help='Treat inputs as video IDs instead of channel handles')
    parser.add_argument('--prompt', '-p', type=str, default='prompt.txt', help='Path to the prompt file for AI summarization (default: prompt.txt)')
    parser.add_argument('--model', '-m', type=str, default='qwen/qwen3-30b-a3b-instruct-2507', help='Model to use for summarization (default: qwen/qwen3-30b-a3b-instruct-2507)')
    parser.add_argument('--include-previous', action='store_true', help='Copy existing summaries from previous datetime folders instead of regenerating them')
    
    args = parser.parse_args()
    
    # 1. Load API keys from environment variables
    load_dotenv()
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

    if not YOUTUBE_API_KEY or not OPENROUTER_API_KEY:
        print("🛑 Error: Please set YOUTUBE_API_KEY and OPENROUTER_API_KEY environment variables.")
        return

    # 2. Parse inputs
    inputs_str = ' '.join(args.inputs)  # Join all input arguments in case they were separated by spaces
    inputs = [item.strip() for item in inputs_str.split(',')]
    days_to_check = args.days

    # 3. Setup
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_check)
    youtube_service = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    
    # Create datetime folder structure
    datetime_folder = create_datetime_folder()
    transcript_dir = os.path.join(datetime_folder, "transcripts")
    summary_dir = os.path.join(datetime_folder, "summaries")
    
    # 4. Collect all videos
    all_videos = []
    
    if args.video_ids:
        # Process as video IDs
        print(f"\nProcessing {len(inputs)} video ID(s)...")
        for video_id in inputs:
            print(f"\n{'='*50}\nFetching video details: {video_id}\n{'='*50}")
            
            video_details = get_video_details(youtube_service, video_id)
            if video_details:
                # Check if this is live content
                if video_details['is_live_content']:
                    print(f"🔴 Skipping live content: {video_details['title']}")
                    continue
                
                # Skip date check when video IDs are provided directly
                # Check if video meets date criteria (only if days filter is meaningful and not using video IDs)
                if not args.video_ids and days_to_check > 0 and video_details['published_at'] < cutoff_date:
                    print(f"⚠️  Video '{video_details['title']}' was published before the cutoff date. Skipping...")
                    continue
                
                all_videos.append(video_details)
                print(f"✅ Added video: {video_details['title']}")
            else:
                print(f"❌ Could not fetch details for video ID: {video_id}")
    else:
        # Process as channel handles
        print(f"\nFetching videos published in the last {days_to_check} day(s)...")
        for channel_handle in inputs:
            print(f"\n{'='*50}\nLooking up channel: {channel_handle}\n{'='*50}")
            
            # Convert channel handle to channel ID
            channel_id = get_channel_id_from_handle(youtube_service, channel_handle)
            
            if not channel_id:
                print(f"❌ Could not find channel ID for '{channel_handle}'. Skipping...")
                continue
            
            print(f"✅ Found channel ID: {channel_id}")
            print(f"\nFetching videos from Channel: {channel_handle} (ID: {channel_id})")
            
            videos = get_channel_videos(youtube_service, channel_id, cutoff_date)
            
            if not videos:
                print(f"No new videos found for channel '{channel_handle}' in the specified period.")
                continue
            
            all_videos.extend(videos)
            print(f"Found {len(videos)} videos from channel '{channel_handle}'")

    if not all_videos:
        print("No videos found to process.")
        return

    print(f"\n🎬 Total videos to process: {len(all_videos)}")
    
    # 5. PHASE 1: Process transcripts with duplicate checking
    print(f"\n{'='*60}\nPHASE 1: PROCESSING TRANSCRIPTS\n{'='*60}")
    
    # Track video IDs processed in this run
    processed_video_ids = []
    skipped_video_ids = []
    
    for i, video in enumerate(all_videos, 1):
        print(f"\n[{i}/{len(all_videos)}] Processing transcript for: {video['title']}")
        
        transcript_filename = os.path.join(transcript_dir, f"{video['id']}_transcript.txt")
        summary_filename = os.path.join(summary_dir, f"{video['id']}_summary.md")
        
        # Check if transcript was already downloaded in other datetime folders
        existing_transcript_path, existing_summary_path = find_existing_transcript(video['id'], datetime_folder)
        
        if existing_transcript_path:
            print(f"🔍 Found existing transcript: {existing_transcript_path}")
            
            # Always copy existing transcript to current datetime folder
            print(f"📋 Copying existing transcript to current folder...")
            shutil.copy2(existing_transcript_path, transcript_filename)
            
            # Only copy existing summary if --include-previous is specified
            if args.include_previous and existing_summary_path:
                print(f"📋 Copying existing summary to current folder...")
                shutil.copy2(existing_summary_path, summary_filename)
            
            processed_video_ids.append(video['id'])
            print(f"✅ Copied existing transcript for video: {video['title']}")
        else:
            # Download new transcript
            print(f"📥 Downloading new transcript...")
            transcript = get_transcript(video['id'])
            
            if transcript:
                # Save transcript to a file
                with open(transcript_filename, 'w', encoding='utf-8') as f:
                    f.write(transcript)
                print(f"✅ Transcript saved to: {transcript_filename}")
                processed_video_ids.append(video['id'])
            else:
                print(f"❌ Could not retrieve transcript for video {video['id']}")

    # 6. PHASE 2: Generate summaries
    print(f"\n{'='*60}\nPHASE 2: GENERATING SUMMARIES\n{'='*60}")
    
    # Track video IDs that were summarized in this run
    summarized_video_ids = []
    
    for i, video in enumerate(all_videos, 1):
        # Skip videos that were not processed in Phase 1
        if video['id'] in skipped_video_ids:
            continue
            
        print(f"\n[{i}/{len(all_videos)}] Processing summary for: {video['title']}")
        
        transcript_filename = os.path.join(transcript_dir, f"{video['id']}_transcript.txt")
        summary_filename = os.path.join(summary_dir, f"{video['id']}_summary.md")
        
        # Skip if summary already exists (from copying in Phase 1)
        if os.path.exists(summary_filename):
            print(f"📄 Summary already exists: {summary_filename}")
            summarized_video_ids.append(video['id'])
            continue
        
        # Check if transcript exists
        if not os.path.exists(transcript_filename):
            print(f"❌ No transcript file found for video {video['id']}. Skipping summary generation.")
            continue
        
        # Load transcript
        with open(transcript_filename, 'r', encoding='utf-8') as f:
            transcript = f.read()
        
        # Generate summary
        print(f"🧠 Summarizing with OpenRouter using model: {args.model} and prompt: {args.prompt}...")
        summary = summarize_with_openrouter(OPENROUTER_API_KEY, transcript, args.prompt, args.model)
        
        # Only proceed if summary generation was successful (not an error message)
        if summary and not summary.startswith("Error:") and not summary.startswith("An error occurred"):
            # Get channel handle if available
            channel_handle = None
            if 'channel_id' in video:
                channel_handle = get_channel_handle_from_id(youtube_service, video['channel_id'])
            
            # Save summary to a file
            with open(summary_filename, 'w', encoding='utf-8') as f:
                f.write(f"Video Title: {video['title']}\n")
                if channel_handle:
                    f.write(f"Channel Handle: {channel_handle}\n")
                f.write(f"Video ID: {video['id']}\n")
                f.write(f"Published At: {video['published_at']}\n")
                f.write(f"Summary Generated At: {datetime.now()}\n")
                f.write("-" * 50 + "\n\n")
                f.write(summary)
            print(f"✅ Summary saved to: {summary_filename}")
            
            # Only add to summarized video IDs list if summary was successfully generated
            summarized_video_ids.append(video['id'])
            
            print("\n📌 **SUMMARY:**")
            print(summary)
        else:
            print(f"❌ Failed to generate summary for video {video['id']}: {summary}")
    
    # Print final results
    print(f"\n{'='*60}")
    print("PROCESSING RESULTS:")
    print(f"📁 Datetime folder: {datetime_folder}")
    print(f"📥 Processed videos: {len(processed_video_ids)}")
    print(f"⏭️  Skipped videos: {len(skipped_video_ids)}")
    print(f"📝 Summarized videos: {len(summarized_video_ids)}")
    
    if summarized_video_ids:
        print(f"\nSUMMARIZED VIDEO IDs:")
        print(','.join(summarized_video_ids))
    
    if skipped_video_ids:
        print(f"\nSKIPPED VIDEO IDs:")
        print(','.join(skipped_video_ids))
        
    print(f"{'='*60}")

if __name__ == '__main__':
    main()

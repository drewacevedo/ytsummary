# YouTube Video Summarizer

A Python tool that automatically downloads transcripts from YouTube videos and generates AI-powered summaries using OpenRouter API. Perfect for quickly extracting key insights from financial, educational, or informational YouTube content.

## Features

- 🎯 **Channel-based Processing**: Fetch videos from YouTube channels using handles (e.g., `@meetandrew`)
- 📹 **Individual Video Processing**: Process specific videos using their YouTube video IDs
- 📅 **Date Filtering**: Only process videos published within a specified number of days
- 📝 **Automatic Transcription**: Extract transcripts using yt-dlp with subtitle support
- 🤖 **AI Summarization**: Generate intelligent summaries using OpenRouter's AI models
- 📁 **Organized Output**: Saves transcripts and summaries in separate directories
- 🔄 **Smart Caching**: Skips already processed videos to save time and API costs
- ⚙️ **Customizable Prompts**: Use external prompt files for different summarization styles

## Prerequisites

Before using this tool, you'll need:

1. **YouTube Data API Key**: Get one from [Google Cloud Console](https://console.cloud.google.com/)
2. **OpenRouter API Key**: Sign up at [OpenRouter](https://openrouter.ai/) for AI summarization

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/youtube-summarizer.git
   cd youtube-summarizer
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   Create a `.env` file in the project root:
   ```env
   YOUTUBE_API_KEY=your_youtube_api_key_here
   OPENROUTER_API_KEY=your_openrouter_api_key_here
   ```

## Usage

### Basic Usage

**Process videos from a YouTube channel (last 7 days):**
```bash
python youtube_summarizer.py @meetandrew --days 7
```

**Process multiple channels:**
```bash
python youtube_summarizer.py "@meetandrew,@codingwithdrew" --days 3
```

**Process specific video IDs:**
```bash
python youtube_summarizer.py dQw4w9WgXcQ --video-ids
```

**Process multiple video IDs:**
```bash
python youtube_summarizer.py "dQw4w9WgXcQ,jNQXAC9IVRw" --video-ids
```

### Command Line Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `inputs` | - | Comma-separated channel handles or video IDs | Required |
| `--days` | `-d` | Number of days to look back for videos | 1 |
| `--video-ids` | `-v` | Treat inputs as video IDs instead of channel handles | False |
| `--prompt` | `-p` | Path to the prompt file for AI summarization | prompt.txt |

### Examples

```bash
# Get videos from the last 24 hours
python youtube_summarizer.py @meetandrew

# Get videos from the last week
python youtube_summarizer.py @meetandrew --days 7

# Process specific videos
python youtube_summarizer.py "dQw4w9WgXcQ,jNQXAC9IVRw" -v

# Multiple channels, last 3 days
python youtube_summarizer.py "@meetandrew,@codingwithdrew,@coffeezilla" -d 3

# Use a custom prompt file
python youtube_summarizer.py @meetandrew --prompt custom_prompt.txt

# Use different prompts for different content types
python youtube_summarizer.py @educationalchannel --prompt educational_prompt.txt
python youtube_summarizer.py @techchannel --prompt tech_prompt.txt
```

## Output Structure

The tool creates two directories:

```
project/
├── transcripts/
│   ├── VIDEO_ID_transcript.txt
│   └── ...
├── summaries/
│   ├── VIDEO_ID_summary.md
│   └── ...
└── prompt.txt
```

### Summary Format

Each summary file includes:
- Video metadata (title, ID, publish date)
- Generation timestamp
- AI-generated summary based on your prompt

## Customizing the AI Prompt

### Using the Default Prompt

The tool comes with a default `prompt.txt` file for general video content. You can edit this file to customize how videos are summarized for your specific needs.

### Using Multiple Prompt Files

You can create different prompt files for different types of content and specify which one to use with the `--prompt` parameter:

**Example prompt files:**

**`educational_prompt.txt`** - For educational content:
```txt
You are an educational content summarizer. Extract key learning points, concepts, and takeaways from the following video transcript. Organize the information in a clear, structured format suitable for study notes.
```

**`tech_prompt.txt`** - For technology content:
```txt
You are a technology analyst. Summarize the following tech video transcript, focusing on new technologies, product announcements, technical specifications, and industry implications.
```

**`news_prompt.txt`** - For news content:
```txt
You are a news summarizer. Extract the key facts, main story points, and important details from the following news video transcript. Present the information in a clear, objective manner.
```

### Using Custom Prompts

```bash
# Use educational prompt for educational channels
python youtube_summarizer.py @khanacademy --prompt educational_prompt.txt

# Use tech prompt for technology channels  
python youtube_summarizer.py @mkbhd --prompt tech_prompt.txt

# Use news prompt for news channels
python youtube_summarizer.py @cnn --prompt news_prompt.txt
```

This flexibility allows you to tailor the AI's summarization style to match the content type and your specific needs.

## Configuration

### Supported Models

The tool uses OpenRouter's `qwen/qwen3-30b-a3b-instruct-2507` model by default. You can change this in the `summarize_with_openrouter()` function:

```python
model="anthropic/claude-3-haiku",  # Example alternative
```

### API Rate Limits

- **YouTube API**: 10,000 units per day (free tier)
- **OpenRouter**: Varies by model and plan

## Troubleshooting

### Common Issues

**"No subtitle files found"**
- The video doesn't have captions/subtitles available
- Try videos with auto-generated captions

**"Channel not found"**
- Ensure the channel handle is correct (with or without @)
- Some channels may not be discoverable via handle

**"API key errors"**
- Verify your `.env` file is properly configured
- Check that your API keys are valid and have sufficient quota

### Debug Tips

1. **Check video availability**: Ensure videos have English subtitles
2. **Verify API keys**: Test them independently
3. **Check date filters**: Videos might be outside your date range

## File Structure

```
youtube-summarizer/
├── youtube_summarizer.py    # Main script
├── requirements.txt         # Python dependencies
├── prompt.txt              # AI summarization prompt
├── .env                    # Environment variables (create this)
├── transcripts/            # Generated transcripts
├── summaries/              # Generated summaries
└── README.md              # This file
```

## Dependencies

- `google-api-python-client`: YouTube Data API
- `yt-dlp`: Video transcript extraction
- `openai`: OpenRouter API client
- `python-dotenv`: Environment variable management

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This tool is for educational and research purposes. Ensure you comply with YouTube's Terms of Service and respect content creators' rights. The AI summaries are generated automatically and may not always be accurate.

---

**Happy Summarizing! 🎬✨**

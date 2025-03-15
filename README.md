# House AI - Twitch Interactive Bot

This project creates an interactive experience where Twitch chat can suggest topics for a dialogue between House and Wilson characters. The system generates AI responses, converts them to speech using TTS, and plays them on a webpage with character animations.

## System Overview

1. **Twitch Integration**: Allows chat to suggest dialogue topics using `!suggest` command
2. **AI Response Generation**: Uses Ollama's dolphin-mistral model to create House/Wilson dialogues
3. **Text-to-Speech**: Converts dialogue to audio using XTTS V2
4. **Web Interface**: Displays characters and subtitles with the current dialogue

## Setup Instructions

### Prerequisites

- Python 3.8+
- CUDA-compatible GPU (recommended for TTS)
- Ollama installed with the dolphin-mistral:7b model
- TTS library with XTTS V2 model

### Installation

1. Clone the repository
2. Install dependencies:
   ```
   pip install flask twitchio torch TTS python-dotenv requests ollama
   ```

3. Create a `.env` file with your Twitch credentials:
   ```
   TWITCH_ACCESS_TOKEN=your_twitch_oauth_token
   TWITCH_CHANNEL=your_channel_name
   ```

4. Create the required directories:
   ```
   mkdir -p voices/input voices/output static
   ```

5. Add reference voice samples:
   - Place a House voice sample at `voices/input/haus.wav`
   - Place a Wilson voice sample at `voices/input/wilson.wav`

6. Add character images:
   - Place House image at `static/house.png`
   - Place Wilson image at `static/wilson.png`

## Running the Application

1. Start the Flask server:
   ```
   python app.py
   ```

2. In a separate terminal, start the main application:
   ```
   python main.py
   ```

3. Open a web browser and navigate to:
   ```
   http://127.0.0.1:1204/
   ```

## How It Works

1. Users in Twitch chat use the `!suggest` command to add topics to the queue
2. The system takes topics from the queue and generates House/Wilson dialogues
3. The dialogues are converted to audio files using TTS
4. The web interface displays the characters and plays the audio
5. When playback completes, the system processes the next topic in the queue
6. If the queue is empty, the system adds default topics

## File Structure

- `app.py`: Flask server for web interface
- `main.py`: Main application logic and Twitch bot
- `main.html`: Web interface
- `static/dialogue.js`: Generated dialogue data for the web interface
- `voices/input/`: Reference voice samples
- `voices/output/`: Generated audio files
- `queue.db`: SQLite database for topic queue

## Troubleshooting

- **No audio playing**: Check that audio files are being generated in `voices/output/`
- **Twitch bot not connecting**: Verify your `.env` file has correct credentials
- **TTS errors**: Ensure you have the XTTS V2 model installed and CUDA available
- **Flask server errors**: Check logs for details, ensure port 1204 is available
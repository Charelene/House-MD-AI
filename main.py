import requests, os, asyncio, re, torch, json, sqlite3, random, ssl, time, shutil
from ollama import AsyncClient
from TTS.api import TTS
from dotenv import load_dotenv
import twitchio
from twitchio.ext import commands

# Load environment variables
load_dotenv(override=True)


# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('queue.db')
    cursor = conn.cursor()

    # Check if in_progress column exists
    cursor.execute("PRAGMA table_info(queue)")
    columns = [column[1] for column in cursor.fetchall()]

    if 'queue' not in columns:  # If table doesn't exist, create it
        cursor.execute('''CREATE TABLE IF NOT EXISTS queue (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        prompt TEXT NOT NULL,
                        user_requested BOOLEAN NOT NULL,
                        in_progress BOOLEAN DEFAULT 0
                    )''')
    elif 'in_progress' not in columns:  # If column doesn't exist, add it
        cursor.execute('ALTER TABLE queue ADD COLUMN in_progress BOOLEAN DEFAULT 0')

    conn.commit()
    conn.close()


def cleanup_queue():
    """Reset all in-progress items and clean up the queue if needed"""
    conn = sqlite3.connect('queue.db')
    cursor = conn.cursor()
    # Reset any items marked as in_progress
    cursor.execute('UPDATE queue SET in_progress = 0 WHERE in_progress = 1')
    conn.commit()
    conn.close()
    print("Queue cleaned up - all in-progress items reset")


async def add_to_queue(prompt, user_requested=False):
    conn = sqlite3.connect('queue.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO queue (prompt, user_requested, in_progress) VALUES (?, ?, 0)', (prompt, user_requested))
    conn.commit()
    queue_id = cursor.lastrowid  # Get the ID of the inserted item
    conn.close()
    return queue_id


async def get_next_from_queue():
    conn = sqlite3.connect('queue.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, prompt FROM queue WHERE in_progress = 0 ORDER BY id ASC LIMIT 1')
    result = cursor.fetchone()
    if result:
        # Mark as in progress
        cursor.execute('UPDATE queue SET in_progress = 1 WHERE id = ?', (result[0],))
        conn.commit()
    conn.close()
    return result


async def remove_from_queue(item_id):
    conn = sqlite3.connect('queue.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM queue WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()


async def generate_ai_response(prompt):
    model = 'dolphin-mistral:7b'
    message = [
        {'role': 'system', 'content': """
            Generate a dialogue between house and wilson in single line; swear words must be included, they both insult each other in every reply. the topic of discussion is the user's prompt
            Minimum 10 lines from characters
            The topic of discussion is the user's prompt.
        """},
        {'role': 'user', 'content': prompt}
    ]
    try:
        response = await AsyncClient().chat(model=model, messages=message)
        return response.message.content if hasattr(response, 'message') and hasattr(response.message,
                                                                                    'content') else "No content"
    except Exception as e:
        print(f"Error generating AI response: {e}")
        return "HOUSE: Damn it, the AI response generator is broken! WILSON: Maybe you should try debugging it."


def format_dialogue_for_tts(ai_output):
    # First pattern: Look for "HOUSE: something WILSON: something"
    dialogue_matches = re.findall(r'HOUSE:\s*(.*?)\s*WILSON:\s*(.*?)(?=$|\nHOUSE:|\. HOUSE:)', ai_output,
                                  re.DOTALL | re.MULTILINE)

    if not dialogue_matches:
        # Fallback pattern: Look for lines that start with HOUSE: or WILSON:
        house_lines = re.findall(r'HOUSE:\s*(.*?)(?=$|\n|\. WILSON:)', ai_output, re.DOTALL | re.MULTILINE)
        wilson_lines = re.findall(r'WILSON:\s*(.*?)(?=$|\n|\. HOUSE:)', ai_output, re.DOTALL | re.MULTILINE)

        # If we found some lines, zip them together
        if house_lines and wilson_lines:
            # Make the lists the same length
            min_len = min(len(house_lines), len(wilson_lines))
            dialogue_matches = [(house_lines[i], wilson_lines[i]) for i in range(min_len)]

    formatted_dialogue = []
    position = 1

    if dialogue_matches:
        for house_line, wilson_line in dialogue_matches:
            formatted_dialogue.append({"character": "HOUSE", "voice_line": house_line.strip(), "position": position})
            position += 1
            formatted_dialogue.append({"character": "WILSON", "voice_line": wilson_line.strip(), "position": position})
            position += 1
    else:
        # If all else fails, create a simple fallback dialogue
        formatted_dialogue = [
            {"character": "HOUSE", "voice_line": "The AI failed to generate a proper dialogue.", "position": 1},
            {"character": "WILSON", "voice_line": "Maybe we should try again with a different prompt.", "position": 2}
        ]

    return formatted_dialogue


async def generate_tts_audio(batch, dialogue_id):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    try:
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

        # Create a dedicated folder for this dialogue
        dialogue_dir = f"voices/dialogue_{dialogue_id}"
        os.makedirs(dialogue_dir, exist_ok=True)

        for item in batch:
            speaker_wav = "voices/input/house.wav" if item["character"] == "HOUSE" else "voices/input/wilson.wav"
            output_file = f"{dialogue_dir}/{item['character'].lower()}_{item['position']}.wav"

            # Ensure the input voice file exists
            if not os.path.exists(speaker_wav):
                print(f"Warning: Speaker file {speaker_wav} not found")
                continue

            tts.tts_to_file(text=item["voice_line"], speaker_wav=speaker_wav, language="en", file_path=output_file)
            print(f"Generated audio file: {output_file}")

        # Create a metadata.json file with the dialogue info
        with open(f"{dialogue_dir}/metadata.json", 'w') as f:
            json.dump({
                "dialogue_id": dialogue_id,
                "created_at": time.time(),
                "dialogue": batch
            }, f)

        print(f"TTS generation complete for dialogue {dialogue_id}")
        return dialogue_dir
    except Exception as e:
        print(f"Error generating TTS audio: {e}")
        return None


def update_webpage_dialogue(dialogue_data, dialogue_id):
    try:
        # Update with the dialogue ID
        for item in dialogue_data:
            item['dialogue_id'] = dialogue_id

        requests.post('http://127.0.0.1:1204/update_dialogue',
                      json={'dialogue': dialogue_data, 'dialogue_id': dialogue_id})
        print(f"Dialogue data sent to web interface for dialogue {dialogue_id}")
    except Exception as e:
        print(f"Error updating dialogue: {e}")


def update_webpage_state(generated_topic=None, current_topic=None, dialogue_id=None):
    data = {}
    if generated_topic is not None:
        data['generatedTopic'] = generated_topic
    if current_topic is not None:
        data['currentTopic'] = current_topic
    if dialogue_id is not None:
        data['dialogue_id'] = dialogue_id

    try:
        requests.post('http://127.0.0.1:1204/update', json=data)
        print(f"Web interface state updated: {data}")
    except Exception as e:
        print(f"Error updating web interface state: {e}")


def cleanup_old_dialogue_folders():
    """Clean up dialogue folders that are older than 6 hours"""
    voices_dir = "voices"
    if not os.path.exists(voices_dir):
        return

    current_time = time.time()
    for item in os.listdir(voices_dir):
        if item.startswith("dialogue_"):
            folder_path = os.path.join(voices_dir, item)
            if os.path.isdir(folder_path):
                # Check metadata file for creation time
                metadata_file = os.path.join(folder_path, "metadata.json")
                if os.path.exists(metadata_file):
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                            created_at = metadata.get('created_at', 0)
                            if current_time - created_at > 21600:  # 6 hours
                                shutil.rmtree(folder_path)
                                print(f"Cleaned up old dialogue folder: {folder_path}")
                    except Exception as e:
                        print(f"Error reading metadata for {folder_path}: {e}")
                        # If metadata is corrupt, check folder modification time
                        if current_time - os.path.getmtime(folder_path) > 21600:
                            shutil.rmtree(folder_path)
                            print(f"Cleaned up old dialogue folder based on mtime: {folder_path}")
                else:
                    # No metadata file, check folder modification time
                    if current_time - os.path.getmtime(folder_path) > 21600:
                        shutil.rmtree(folder_path)
                        print(f"Cleaned up old dialogue folder: {folder_path}")


class TwitchBot(commands.Bot):
    def __init__(self):
        # Fix environment variable names
        token = os.getenv('TWITCH_ACCESS_KEY')
        channel = os.getenv('TWITCH_CHANNEL_NAME')

        if not token or not channel:
            print("Warning: Twitch credentials not found in .env file")
            token = token or "dummy_token"
            channel = channel or "dummy_channel"

        # Configure SSL context to handle certificate issues
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        super().__init__(
            token=token,
            prefix='!',
            initial_channels=[channel],
            ssl_context=ssl_context
        )
        # Initialize with a dummy task to prevent NoneType errors
        self.queue_processor_task = asyncio.create_task(asyncio.sleep(0))

    async def event_ready(self):
        print(f'Logged in as {self.nick}')
        # Cancel previous task if it exists
        if self.queue_processor_task:
            self.queue_processor_task.cancel()
        # Start the queue processor when the bot is ready
        self.queue_processor_task = asyncio.create_task(run_queue_processor())

    async def event_message(self, message):
        if message.author and message.author.name.lower() != self.nick.lower():
            await self.handle_commands(message)

    @commands.command(name='suggest')
    async def suggest(self, ctx: commands.Context):
        prompt = ctx.message.content[len('!suggest '):].strip()
        if prompt:
            queue_id = await add_to_queue(prompt, user_requested=True)
            await ctx.send(f'Added suggestion: "{prompt}" to the queue (ID: {queue_id}).')
        else:
            await ctx.send('Usage: !suggest <prompt>')


# Global variable to track if a dialogue is currently playing
dialogue_playing = False


async def run_queue_processor():
    try:
        global dialogue_playing
        dialogue_playing = False

        # List of default prompts to choose from randomly
        default_prompts = [
            "House's opinion on modern medicine",
            "Wilson dealing with House's antics",
            "The ethics of experimental treatments",
            "House's addiction to Vicodin",
            "Unusual medical cases"
        ]

        # Check if queue is empty and add a random default prompt if needed
        conn = sqlite3.connect('queue.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM queue')
        count = cursor.fetchone()[0]
        conn.close()

        if count == 0:
            print("Queue is empty, adding a random default prompt")
            random_prompt = random.choice(default_prompts)
            await add_to_queue(random_prompt, user_requested=False)

        print("Queue processor started")

        # Run cleanup once at startup
        cleanup_old_dialogue_folders()
        last_cleanup_time = time.time()

        while True:
            # Run cleanup every hour
            current_time = time.time()
            if current_time - last_cleanup_time > 3600:  # 1 hour
                cleanup_old_dialogue_folders()
                last_cleanup_time = current_time

            # If a dialogue is playing, wait before processing the next item
            if dialogue_playing:
                print("A dialogue is currently playing, waiting...")
                await asyncio.sleep(5)
                continue

            next_item = await get_next_from_queue()

            if next_item:
                item_id, prompt = next_item
                print(f"Processing queue item {item_id}: {prompt}")

                # Update webpage to show what's being generated
                update_webpage_state(generated_topic=prompt)

                # Generate dialogue
                ai_output = await generate_ai_response(prompt)
                formatted_dialogue = format_dialogue_for_tts(ai_output)

                # Generate TTS audio in a dedicated folder
                dialogue_dir = await generate_tts_audio(formatted_dialogue, item_id)

                if dialogue_dir:
                    # Set global flag that a dialogue is playing
                    dialogue_playing = True

                    # Update dialogue.js for the webpage
                    update_webpage_dialogue(formatted_dialogue, item_id)

                    # Update webpage state to show current topic and dialogue ID
                    update_webpage_state(generated_topic="", current_topic=prompt, dialogue_id=item_id)

                    # Remove the item from the queue
                    await remove_from_queue(item_id)
                else:
                    print(f"Failed to generate TTS for dialogue {item_id}")
                    # Reset the in_progress flag for this item
                    conn = sqlite3.connect('queue.db')
                    cursor = conn.cursor()
                    cursor.execute('UPDATE queue SET in_progress = 0 WHERE id = ?', (item_id,))
                    conn.commit()
                    conn.close()
            else:
                # No items in queue, add a random default prompt
                print("Queue is empty, adding a random default prompt")
                random_prompt = random.choice(default_prompts)
                await add_to_queue(random_prompt, user_requested=False)
                # Wait a bit before checking again
                await asyncio.sleep(5)
    except Exception as e:
        print(f"Error in queue processor: {e}")
        # Restart the queue processor after a delay
        await asyncio.sleep(5)
        asyncio.create_task(run_queue_processor())


# Function to handle playback finished notification
async def handle_playback_finished():
    global dialogue_playing
    dialogue_playing = False
    print("Received playback finished notification, ready for next dialogue")


async def main_async():
    try:
        # Initialize the database
        init_db()

        # Clean up any in-progress queue items
        cleanup_queue()

        # Make sure directories exist
        os.makedirs("voices/input", exist_ok=True)
        os.makedirs("static", exist_ok=True)

        # Start the queue processor
        queue_task = asyncio.create_task(run_queue_processor())

        # Start the Twitch bot with error handling
        try:
            bot = TwitchBot()
            await bot.start()
        except Exception as e:
            print(f"Error starting Twitch bot: {e}")
            print("Continuing without Twitch integration")

        # Make sure the queue processor stays running
        await queue_task
    except Exception as e:
        print(f"Error in main_async: {e}")


def main():
    # Use asyncio to run the async main function
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("Program terminated by user")
    except Exception as e:
        print(f"Error in main function: {e}")


if __name__ == "__main__":
    main()
import requests, os, asyncio, re, torch, json, sqlite3
from flask import Flask, request, jsonify
from TTS.api import TTS
from ollama import AsyncClient
from dotenv import load_dotenv
import wave
import numpy as np
import twitchio
from twitchio.ext import commands

# Load environment variables
load_dotenv(override=True)

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('queue.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS queue (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        prompt TEXT NOT NULL,
                        user_requested BOOLEAN NOT NULL
                    )''')
    conn.commit()
    conn.close()


async def add_to_queue(prompt, user_requested=False):
    conn = sqlite3.connect('queue.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO queue (prompt, user_requested) VALUES (?, ?)', (prompt, user_requested))
    conn.commit()
    conn.close()


async def get_next_from_queue():
    conn = sqlite3.connect('queue.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, prompt FROM queue ORDER BY id ASC LIMIT 1')
    result = cursor.fetchone()
    if result:
        cursor.execute('DELETE FROM queue WHERE id = ?', (result[0],))
        conn.commit()
    conn.close()
    return result


async def generate_ai_response(prompt):
    model = 'dolphin-mistral:7b'
    message = [
        {'role': 'system', 'content': """
            Generate a dialogue between House and Wilson in a single line format.
            Minimum 10 lines
            Example: "HOUSE: Insult. WILSON: Retort."
            Always include swear words, and keep the exchange combative and humorous.
            The topic of discussion is the user's prompt.
        """},
        {'role': 'user', 'content': prompt}
    ]
    response = await AsyncClient().chat(model=model, messages=message)
    return response.message.content if hasattr(response, 'message') and hasattr(response.message,
                                                                                'content') else "No content"


def format_dialogue_for_tts(ai_output):
    dialogue_lines = re.findall(r'HOUSE: .*? WILSON: .*?', ai_output)
    formatted_dialogue = []
    for position, line in enumerate(dialogue_lines):
        parts = line.split(" WILSON: ")
        formatted_dialogue.append({"character": "HOUSE", "voice_line": parts[0][7:], "position": position * 2 + 1})
        formatted_dialogue.append({"character": "WILSON", "voice_line": parts[1], "position": position * 2 + 2})
    return formatted_dialogue


async def generate_tts_audio(batch):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
    for item in batch:
        speaker_wav = "voices/input/haus.wav" if item["character"] == "HOUSE" else "voices/input/wilson.wav"
        output_file = f"voices/output/{item['character'].lower()}_{item['position']}.wav"
        tts.tts_to_file(text=item["voice_line"], speaker_wav=speaker_wav, language="en", file_path=output_file)
    print("TTS generation complete.")


class TwitchBot(commands.Bot):
    def __init__(self):
        super().__init__(token=os.getenv('TWITCH_ACCESS_TOKEN'), prefix='!',
                         initial_channels=[os.getenv('TWITCH_CHANNEL')])

    async def event_ready(self):
        print(f'Logged in as {self.nick}')

    async def event_message(self, message):
        if message.author.name.lower() != self.nick.lower():
            await self.handle_commands(message)

    @commands.command(name='suggest')
    async def suggest(self, ctx: commands.Context):
        prompt = ctx.message.content[len('!suggest '):].strip()
        if prompt:
            await add_to_queue(prompt, user_requested=True)
            await ctx.send(f'Added suggestion: "{prompt}" to the queue.')
        else:
            await ctx.send('Usage: !suggest <prompt>')


def main():
    init_db()
    bot = TwitchBot()
    asyncio.create_task(run_loop())
    bot.run()


async def run_loop():
    while True:
        next_topic = await get_next_from_queue()
        if next_topic:
            prompt = next_topic[1]
            print(f"Generating for prompt: {prompt}")
            requests.post('http://127.0.0.1:1204/update', json={'generatedTopic': prompt})
            ai_output = await generate_ai_response(prompt)
            formatted_dialogue = format_dialogue_for_tts(ai_output)
            await generate_tts_audio(formatted_dialogue)
            requests.post('http://127.0.0.1:1204/update', json={'currentTopic': prompt})
        await asyncio.sleep(5)


if __name__ == "__main__":
    main()

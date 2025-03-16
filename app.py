from flask import Flask, request, jsonify, send_from_directory
import os, json, asyncio
import main as main_module  # Import the main module to access global variables

app = Flask(__name__)

# Global variables to store current state
current_state = {
    "currentTopic": "",
    "generatedTopic": "",
    "dialogue_id": None
}


# Serve main.html
@app.route('/')
def serve_html():
    return send_from_directory('.', 'main.html')


@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)


# Add dedicated route for dialogue audio files
@app.route('/voices/dialogue_<int:dialogue_id>/<path:filename>')
def serve_dialogue_audio(dialogue_id, filename):
    return send_from_directory(f'voices/dialogue_{dialogue_id}', filename)


# Handle playback finished notification
@app.route('/playback_finished', methods=['POST'])
def playback_finished():
    print("Playback finished notification received.")

    # Reset the dialogue_playing flag in main.py
    asyncio.run(main_module.handle_playback_finished())

    return jsonify({"status": "success"})


@app.route('/update', methods=['POST'])
def update():
    data = request.json
    if 'generatedTopic' in data:
        current_state['generatedTopic'] = data['generatedTopic']
    if 'currentTopic' in data:
        current_state['currentTopic'] = data['currentTopic']
    if 'dialogue_id' in data:
        current_state['dialogue_id'] = data['dialogue_id']
    print(f"State updated: {current_state}")
    return jsonify({"status": "success"})


@app.route('/get_state', methods=['GET'])
def get_state():
    return jsonify(current_state)


@app.route('/update_dialogue', methods=['POST'])
def update_dialogue():
    data = request.json
    dialogue_data = data.get('dialogue', [])
    dialogue_id = data.get('dialogue_id')

    if not dialogue_id:
        return jsonify({"status": "error", "message": "No dialogue_id provided"}), 400

    # Update dialogue data to include dialogue_id and folder path
    for item in dialogue_data:
        if 'dialogue_id' not in item:
            item['dialogue_id'] = dialogue_id

    # Write dialogue data to a JavaScript file that the HTML can load
    with open('static/dialogue.js', 'w') as f:
        f.write(f"const dialogue = {json.dumps(dialogue_data, indent=2)};\n")
        f.write(f"const dialogueId = {dialogue_id};\n")

    return jsonify({"status": "success"})


if __name__ == "__main__":
    # Make sure directories exist
    os.makedirs('static', exist_ok=True)

    # Create empty dialogue.js if it doesn't exist
    if not os.path.exists('static/dialogue.js'):
        with open('static/dialogue.js', 'w') as f:
            f.write("const dialogue = [];\n")
            f.write("const dialogueId = null;\n")

    app.run(host="127.0.0.1", port=1204, debug=True)
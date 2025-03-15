from flask import Flask, request, jsonify, send_from_directory
import os, json

app = Flask(__name__)

# Global variables to store current state
current_state = {
    "currentTopic": "",
    "generatedTopic": ""
}


# Serve main.html
@app.route('/')
def serve_html():
    return send_from_directory('.', 'main.html')


@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)


# Add dedicated route for audio files
@app.route('/voices/output/<path:filename>')
def serve_audio(filename):
    return send_from_directory('voices/output', filename)


@app.route('/delete_audio', methods=['POST'])
def delete_audio():
    data = request.json
    file_path = data.get('file')
    print(f"Attempting to delete file: {file_path}")
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"Successfully deleted: {file_path}")
            return jsonify({"status": "success", "message": f"Deleted {file_path}"})
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    print(f"File not found or already deleted: {file_path}")
    return jsonify({"status": "success", "message": "File already deleted or not found"})


# Handle playback finished notification
@app.route('/playback_finished', methods=['POST'])
def playback_finished():
    print("Playback finished notification received.")
    return jsonify({"status": "success"})


@app.route('/update', methods=['POST'])
def update():
    data = request.json
    if 'generatedTopic' in data:
        current_state['generatedTopic'] = data['generatedTopic']
    if 'currentTopic' in data:
        current_state['currentTopic'] = data['currentTopic']
    print(f"State updated: {current_state}")
    return jsonify({"status": "success"})


@app.route('/get_state', methods=['GET'])
def get_state():
    return jsonify(current_state)


@app.route('/update_dialogue', methods=['POST'])
def update_dialogue():
    data = request.json
    dialogue_data = data.get('dialogue', [])

    # Write dialogue data to a JavaScript file that the HTML can load
    with open('static/dialogue.js', 'w') as f:
        f.write(f"const dialogue = {json.dumps(dialogue_data, indent=2)};")

    return jsonify({"status": "success"})


if __name__ == "__main__":
    # Make sure directories exist
    os.makedirs('voices/output', exist_ok=True)
    os.makedirs('static', exist_ok=True)

    # Create empty dialogue.js if it doesn't exist
    if not os.path.exists('static/dialogue.js'):
        with open('static/dialogue.js', 'w') as f:
            f.write("const dialogue = [];")

    app.run(host="127.0.0.1", port=1204, debug=True)

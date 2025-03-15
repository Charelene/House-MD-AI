from flask import Flask, request, jsonify
import main, os

app = Flask(__name__)

# Serve main.html
@app.route('/')
def serve_html():
    return main.send_from_directory('.', 'main.html')

@app.route('/delete_audio', methods=['POST'])
def delete_audio():
    data = request.json
    file_path = data.get('file')
    if file_path and os.path.exists(file_path):
        os.remove(file_path)
        return jsonify({"status": "success", "message": f"Deleted {file_path}"})
    return jsonify({"status": "error", "message": "File not found"}), 404

# Handle playback finished notification
@app.route('/playback_finished', methods=['POST'])
def playback_finished():
    print("Playback finished notification received.")
    return jsonify({"status": "success"})

@app.route('/update', methods=['POST'])
def update():
    print("Playback finished notification received.")
    return jsonify({"status": "success"})

app.run(host="127.0.0.1", port=1204, debug=True)

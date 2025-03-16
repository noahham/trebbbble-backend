from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from scripts import main

app = Flask(__name__)
CORS(app)

@app.route("/", methods=["GET"])
def home():
    return "Flask API is running. Use POST /process."

@app.route('/process', methods=['POST'])
def process():
    print(request.get_json())
    url = request.get_json()['url']

    if not url:
        return jsonify({
            'error': 'No URL provided',
            'success': False
        }), 400

    try:
        return jsonify(main.main(url))

    except Exception as e:
        return jsonify({
            'errora': str(e),
            'success': False
        }), 500

@app.route('/media/cover.jpg')
def media_files():
    return send_from_directory('media', 'cover.jpg')

if __name__ == '__main__':
    app.run()
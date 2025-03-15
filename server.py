from flask import Flask, request, jsonify
from flask_cors import CORS
from scripts import main

app = Flask(__name__)
CORS(app)

@app.route('/process', methods=['POST'])
def process():
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
            'error': str(e),
            'success': False
        }), 500

if __name__ == '__main__':
    app.run()
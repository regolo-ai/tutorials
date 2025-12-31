from flask import Flask, request, jsonify
import uuid
import threading
import os
from crew import product_launch_crew

app = Flask(__name__)
jobs = {}  # In-memory job storage (use Redis in production)

def run_crew_async(job_id, inputs):
    """Execute crew in background thread"""
    try:
        result = product_launch_crew.kickoff(inputs=inputs)
        jobs[job_id] = {
            "status": "completed", 
            "result": str(result),
            "inputs": inputs
        }
    except Exception as e:
        jobs[job_id] = {
            "status": "failed", 
            "error": str(e),
            "inputs": inputs
        }

@app.route('/kickoff', methods=['POST'])
def kickoff():
    """Start a new product launch crew execution"""
    data = request.json
    product_name = data.get('product_name', 'New Product')
    market_segment = data.get('market_segment', 'General Market')

    # Generate unique job ID
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "running", "result": None}

    # Run crew in background
    inputs = {
        "product_name": product_name,
        "market_segment": market_segment
    }
    thread = threading.Thread(target=run_crew_async, args=(job_id, inputs))
    thread.start()

    return jsonify({
        "job_id": job_id,
        "status": "running",
        "message": "Product launch crew initiated"
    }), 202

@app.route('/status/<job_id>', methods=['GET'])
def get_status(job_id):
    """Poll job status and retrieve results"""
    job = jobs.get(job_id, {"status": "not_found"})
    return jsonify(job)

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

import argparse
from functools import partial
import http.server
import socketserver
from pathlib import Path

def serve(directory: Path, port: int):
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        print(f"Report server running at http://127.0.0.1:{port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping report server.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--dir", type=Path, required=True)
    args = parser.parse_args()
    serve(args.dir, args.port)

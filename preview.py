"""Run the real PDF app under the Sites preview daemon."""
import argparse
import os
import uvicorn

parser = argparse.ArgumentParser()
parser.add_argument('--host', default='0.0.0.0')
parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '3000')))
args, _ = parser.parse_known_args()
uvicorn.run('backend.app:app', host=args.host, port=args.port, workers=1)

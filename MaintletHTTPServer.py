import http.server
import socketserver
from MaintletConfig import HTTPPort
from MaintletLog import logger
import psutil

PORT = HTTPPort

Handler = http.server.SimpleHTTPRequestHandler

def run():
    process = psutil.Process()
    process.cpu_affinity([2])
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.error(f"MaintletHTTPServer KeyboardInterrupt")

if __name__ == '__main__':
    run()

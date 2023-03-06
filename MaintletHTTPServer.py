import http.server
import socketserver
from MaintletConfig import HTTPPort
from MaintletLog import logger

PORT = HTTPPort

Handler = http.server.SimpleHTTPRequestHandler

def run():
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.error(f"MaintletHTTPServer KeyboardInterrupt")

if __name__ == '__main__':
    run()
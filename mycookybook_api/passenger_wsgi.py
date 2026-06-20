import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

try:
    from app import app as application
except Exception as e:
    import traceback
    def application(environ, start_response):
        start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
        return [traceback.format_exc().encode()]
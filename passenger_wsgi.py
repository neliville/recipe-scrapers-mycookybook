"""Entry point WSGI Passenger — racine du dépôt (Option A).

Charge mycookybook_api/passenger_wsgi.py sans modifier le code métier existant.
Voir docs/O2SWITCH_DEPLOYMENT_AUDIT.md
"""
import imp
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

wsgi = imp.load_source("wsgi", "mycookybook_api/passenger_wsgi.py")
application = wsgi.application

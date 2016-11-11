#!/usr/bin/python
import sys
import logging
logging.basicConfig(stream=sys.stderr)
sys.path.insert(0,"/var/www/ShoprAPI/")

from api import app as application
application.secret_key = 'cb74517602a13d66c219a8df9fbf026672b1ca1675ff324c8b5346f2da43a1ba'

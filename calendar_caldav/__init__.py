from . import models
from . import controllers
from .hooks import post_init_hook, install_body_capture

# The WSGI body capture has to be in place before the first request is
# served, and post_init_hook only runs on install — not on upgrade, and not
# on a plain restart. Installing it at import time is the only point that
# covers all three.
install_body_capture()

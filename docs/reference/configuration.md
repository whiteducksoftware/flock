# This will automatically load .env file if it exists
from flock import Flock

flock = Flock()  # Will use DEFAULT_MODEL from .env if available
# 02-core-concepts/02-pydantic-types.py
"""
Purpose: Demonstrate using images in Flock
"""

import os

from flock.core import Flock, FlockFactory

MODEL = "azure/gpt-4.1"

flock = Flock(model=MODEL)


# A whimsical agent that turns any sentence into Yoda-speak.
yoda_agent = FlockFactory.create_default_agent(
    name="yoda_translator",
    input="text",
    output="yoda_text",
)
flock.add_agent(yoda_agent)


# --------------------------------
# 2. Run Flock as a REST API
# --------------------------------


# This will start the Flock as a REST API and a UI
# It will also create a OpenAPI spec
# http://localhost:8344/docs

flock.serve()


# --- YOUR TURN! ---
# set chat=True to enable the chat interface
# http://localhost:8344/chat
# try executing "flock --web" or "flock --chat" or both in your terminal

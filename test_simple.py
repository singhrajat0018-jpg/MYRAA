#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'desktop_agent'))
from desktop_agent.brain.ai.ai_manager import AIManager
ai = AIManager()
print("how are you doing:", ai._determine_complexity_hints("", "how are you doing"))
print("let's discuss the project:", ai._determine_complexity_hints("", "let's discuss the project"))
print("strategies for learning:", ai._determine_complexity_hints("", "strategies for learning"))
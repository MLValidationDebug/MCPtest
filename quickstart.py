"""
Quick Start Guide for MCP Chat Demo
"""

# Installation
print("Installing dependencies...")
# pip install -r requirements.txt

# Set your API key
import os
os.environ["LLM_GATEWAY_KEY"] = "edbc8e18adab4c01b3c9c526db4f64e0"

# Run the app
# python app.py

# The chat UI will open in your browser at http://localhost:7860

# Example queries to try:
examples = [
    "What's 25 times 8?",
    "Calculate 100 divided by 4 plus 10",
    "Create a note titled 'Shopping List' with content 'Milk, Eggs, Bread'",
    "List all my notes",
    "What time is it in Tokyo?",
    "What time is it in New York?",
    "Show me available timezones",
]

print("\n📝 Example queries to try:")
for i, example in enumerate(examples, 1):
    print(f"{i}. {example}")

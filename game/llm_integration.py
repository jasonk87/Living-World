# game/llm_integration.py
from typing import TYPE_CHECKING
from . import config # Import the configuration
import json # For constructing payload

if TYPE_CHECKING:
    from .character import Character
    # This import is tricky because world imports character, and character imports llm_integration (which might import world for context)
    # To avoid circular dependency for type hinting if world context is needed here, it's safer to pass world attributes directly.
    # from .world import World

def _remove_thinking_tags(text: str) -> str:
    # Basic removal of <thinking>...</thinking> tags
    import re
    return re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL).strip()

def generate_dialogue(character_a: 'Character', character_b: 'Character', context_prompt: str, world_weather: str = "normal") -> str: # Added world_weather
    if config.USE_LLM:
        prompt = f"System: You are generating a single line of dialogue for a character in a fantasy village simulation game. The character should sound natural based on their personality and traits. The dialogue should be concise, fitting for a brief interaction.\n"
        prompt += f"Character A (Speaker): {character_a.name}, Personality: {character_a.personality}, Traits: {', '.join(character_a.traits)}\n"
        prompt += f"Character B (Listener): {character_b.name}, Personality: {character_b.personality}, Traits: {', '.join(character_b.traits)}\n"
        prompt += f"Situation: {character_a.name} and {character_b.name} are interacting. {context_prompt}\n"
        prompt += f"The current weather is: {world_weather}.\n"
        prompt += f"Generate one line of dialogue for {character_a.name} to say to {character_b.name}:"

        payload = {
            "model": config.LLM_MODEL,
            "prompt": prompt,
            "stream": False
        }

        print(f"--- LLM SIMULATION (FOR {character_a.name}) ---")
        print(f"Attempting to send to LLM Endpoint: {config.LLM_ENDPOINT}")
        print(f"Model: {config.LLM_MODEL}")
        # print(f"Payload: {json.dumps(payload, indent=2)}") # Can be very verbose

        # Actual HTTP request would go here, e.g., using 'requests' library
        # import requests
        # try:
        #     response = requests.post(config.LLM_ENDPOINT, json=payload, timeout=10)
        #     response.raise_for_status()
        #     llm_response_data = response.json()
        #     generated_text = llm_response_data.get("response", "").strip()
        #     if config.LLM_HAS_THINKING_TAGS:
        #         generated_text = _remove_thinking_tags(generated_text)
        #     if not generated_text:
        #        return f"(LLM Error: Empty response from {character_a.name})"
        #     print(f"Actual LLM Response for {character_a.name}: {generated_text}")
        #     return generated_text
        # except requests.exceptions.RequestException as e:
        #     print(f"LLM Request Failed for {character_a.name}: {e}")
        #     return f"({character_a.name} mutters something about the connection being faulty...)"
        # --- End of actual HTTP request block ---

        # Placeholder for when actual HTTP request is commented out
        simulated_response = f"Well met, {character_b.name}."
        if "first time" in context_prompt.lower():
            simulated_response = f"Greetings, {character_b.name}. A fine day, despite the {world_weather}."
        elif "responding to" in context_prompt.lower():
             simulated_response = f"Indeed, {character_b.name}."

        # Add some personality touches to placeholder
        if "gruff" in character_a.personality:
            simulated_response = f"Hmph. {character_b.name}."
            if "first time" in context_prompt.lower():
                 simulated_response = f"You're {character_b.name}, is it? Hmph."
        elif "kind" in character_a.personality:
            if "first time" in context_prompt.lower():
                simulated_response = f"A pleasure to meet you, {character_b.name}!"
            else:
                simulated_response = f"Good to see you again, {character_b.name}!"


        if config.LLM_HAS_THINKING_TAGS: # Example of how thinking tags might be added by an LLM
            simulated_response = f"<thinking>I see {character_b.name}. I should say something appropriate for my {character_a.personality} nature.</thinking> {simulated_response}"
            simulated_response = _remove_thinking_tags(simulated_response) # And then removed

        print(f"Simulated LLM Response for {character_a.name}: {simulated_response}")
        print(f"--- END LLM SIMULATION (FOR {character_a.name}) ---")
        return simulated_response

    else: # USE_LLM is False, use basic placeholder logic
        if "first meeting" in context_prompt.lower(): # Changed key to match character.py
            return f"Greetings, {character_b.name}. Well met."
        elif "again" in context_prompt.lower():
            return f"Hello again, {character_b.name}."
        elif "responding to" in context_prompt.lower():
            return f"Indeed, {character_b.name}."
        else:
            # Fallback placeholder, using world_weather passed to function
            return f"The weather is {world_weather} today, {character_b.name}."

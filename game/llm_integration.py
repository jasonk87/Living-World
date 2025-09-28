# game/llm_integration.py
from typing import TYPE_CHECKING, Dict, Optional, Any
from . import config # Import the configuration
import json # For constructing payload
import random
import urllib.request
import urllib.error

if TYPE_CHECKING:
    from .character import Character
    # This import is tricky because world imports character, and character imports llm_integration (which might import world for context)
    # To avoid circular dependency for type hinting if world context is needed here, it's safer to pass world attributes directly.
    # from .world import World

def _remove_thinking_tags(text: str) -> str:
    import re
    return re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL).strip()


def _call_llm(payload: Dict[str, Any]) -> Optional[str]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        config.LLM_ENDPOINT,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError):
        return None

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return None

    candidate = parsed.get("response") or parsed.get("text") or parsed.get("message")
    if not candidate:
        return None

    if config.LLM_HAS_THINKING_TAGS:
        candidate = _remove_thinking_tags(candidate)

    candidate = candidate.strip()
    return candidate or None


def _classify_context(context_prompt: str) -> str:
    prompt_lower = context_prompt.lower()
    if any(keyword in prompt_lower for keyword in ["first", "introduc", "meeting"]):
        return "introduction"
    if any(keyword in prompt_lower for keyword in ["again", "reunion", "catching"]):
        return "reunion"
    if any(keyword in prompt_lower for keyword in ["respond", "reply", "answer"]):
        return "response"
    if any(keyword in prompt_lower for keyword in ["concern", "trouble", "issue", "worry"]):
        return "concern"
    if any(keyword in prompt_lower for keyword in ["celebrate", "victory", "success"]):
        return "celebration"
    return "casual"


def _describe_weather(weather: str) -> str:
    weather_lower = weather.lower()
    mapping = {
        "sunny": "The sun treats us kindly today",
        "rain": "These rains should fatten the fields",
        "rainy": "These rains should fatten the fields",
        "storm": "That storm could unsettle the outer farms",
        "snow": "The snow is biting, keep warm",
        "snowy": "The snow is biting, keep warm",
        "cloud": "The clouds hang low over the hold",
    }
    return mapping.get(weather_lower, f"The weather sits {weather_lower}")


def _derive_persona(character: 'Character') -> Dict[str, str]:
    personality_lower = character.personality.lower()
    base = {
        "greeting": "Well met",
        "acknowledge": "Aye",
        "casual": "",
        "concern": "",
    }

    if "stern" in personality_lower or "gruff" in personality_lower:
        base.update({
            "greeting": "Hmph",
            "acknowledge": "Right",
            "casual": "No sense dawdling",
            "concern": "We must keep discipline",
        })
    elif "kind" in personality_lower or "warm" in personality_lower:
        base.update({
            "greeting": "Warm greetings",
            "acknowledge": "Of course",
            "casual": "It's good to share a moment",
            "concern": "I worry for our neighbours",
        })
    elif "scholar" in personality_lower or "thoughtful" in personality_lower:
        base.update({
            "greeting": "Ah, hello",
            "acknowledge": "Indeed",
            "casual": "Let us consider the day's lessons",
            "concern": "We should study this problem",
        })
    elif "cheer" in personality_lower or "boisterous" in personality_lower:
        base.update({
            "greeting": "Ho there",
            "acknowledge": "Ha!",
            "casual": "Spirits are high",
            "concern": "We won't let trouble sink us",
        })

    if "Generous" in character.traits:
        base.setdefault("casual", "")
        base["casual"] = (base["casual"] + " Let's share what we can.").strip()
    if "Cautious" in character.traits:
        base.setdefault("concern", "")
        base["concern"] = (base["concern"] + " We must tread carefully.").strip()
    if "Optimistic" in character.traits:
        base.setdefault("casual", "")
        optimistic_line = " There's always a brighter turn coming."
        if optimistic_line.strip() not in base["casual"]:
            base["casual"] = (base["casual"] + optimistic_line).strip()
    return base


def _build_offline_dialogue(
    character_a: 'Character',
    character_b: 'Character',
    context_prompt: str,
    world_weather: str,
) -> str:
    context = _classify_context(context_prompt)
    persona = _derive_persona(character_a)
    weather_fragment = _describe_weather(world_weather)
    weather_clause = f" {weather_fragment}." if weather_fragment else ""

    templates = {
        "introduction": [
            "{greeting}, {other_name}. I'm {self_name}, and I keep an eye on these lands.{weather}",
            "{greeting}, {other_name}. May our work go smoothly.{weather}",
        ],
        "reunion": [
            "{acknowledge}, {other_name}. It's good to cross paths again.{weather}",
            "{acknowledge}! I've been meaning to hear how you're faring, {other_name}.{weather}",
        ],
        "response": [
            "{acknowledge}, I hear you. {follow_up}{weather}",
            "{acknowledge}. Let's keep matters steady.{weather}",
        ],
        "concern": [
            "{concern_line} I'll see that it's handled.{weather}",
            "{acknowledge}. I'll put word out—no one stands alone.{weather}",
        ],
        "celebration": [
            "{acknowledge}! News like this keeps folk thriving.{weather}",
            "{greeting}! We'll mark this success properly soon.{weather}",
        ],
        "casual": [
            "{greeting}, {other_name}. {casual_line}{weather}",
            "{greeting}. {casual_line}{weather}",
        ],
    }

    chosen_templates = templates.get(context, templates["casual"])
    template = random.choice(chosen_templates)

    follow_up_options = [
        "I'll see what the ledgers say.",
        "Let's check the stockpiles before dusk.",
        "We should brief the crew at the workshop.",
    ]
    follow_up = random.choice(follow_up_options)
    casual_line = persona.get("casual") or "The day keeps us busy."
    concern_line = persona.get("concern") or "I'll not ignore this."

    rendered = template.format(
        greeting=persona.get("greeting", "Greetings"),
        acknowledge=persona.get("acknowledge", "Aye"),
        concern_line=concern_line,
        casual_line=casual_line,
        follow_up=follow_up,
        other_name=character_b.name,
        self_name=character_a.name,
        weather=weather_clause,
    )
    return rendered.strip()


def generate_dialogue(
    character_a: 'Character',
    character_b: 'Character',
    context_prompt: str,
    world_weather: str = "normal",
) -> str:
    if config.USE_LLM:
        prompt = (
            "System: You are generating a single line of dialogue for a character in a fantasy settlement simulation. "
            "Respond in the character's voice and keep the line under 40 words.\n"
            f"Speaker: {character_a.name}. Personality: {character_a.personality}. Traits: {', '.join(character_a.traits)}.\n"
            f"Listener: {character_b.name}. Personality: {character_b.personality}. Traits: {', '.join(character_b.traits)}.\n"
            f"Context: {context_prompt}. Weather: {world_weather}.\n"
            f"Compose the spoken line for {character_a.name}:"
        )
        payload = {"model": config.LLM_MODEL, "prompt": prompt, "stream": False}
        llm_line = _call_llm(payload)
        if llm_line:
            return llm_line

    return _build_offline_dialogue(character_a, character_b, context_prompt, world_weather)

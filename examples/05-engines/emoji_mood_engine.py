from __future__ import annotations

import asyncio
from collections import Counter

from pydantic import BaseModel, Field

from flock import Flock, flock_type
from flock.components import EngineComponent
from flock.runtime import EvalInputs, EvalResult


@flock_type(name="MoodPrompt")
class MoodPrompt(BaseModel):
    speaker: str = Field(description="Who is sharing the feeling")
    message: str = Field(description="What they said out loud")


@flock_type(name="MoodEmoji")
class MoodEmoji(BaseModel):
    speaker: str = Field(description="Original speaker")
    detected_mood: str = Field(description="The mood we detected")
    emoji: str = Field(description="Emoji that captures the feeling")
    explanation: str = Field(description="Why we chose this emoji")


class EmojiMoodEngine(EngineComponent):
    """Tiny engine that turns plain text into emoji-coded vibes."""

    MOOD_KEYWORDS: dict[str, set[str]] = {
        "celebratory": {"congrats", "celebrate", "party", "promotion", "win"},
        "love-struck": {"love", "adore", "crush", "hearts", "romance"},
        "adventurous": {"quest", "explore", "adventure", "journey", "discover"},
        "anxious": {"nervous", "worried", "anxious", "deadline", "yikes"},
        "sleepy": {"tired", "zzz", "sleepy", "pillow", "nap"},
        "mischievous": {"prank", "secret", "plot", "mischief", "scheme"},
    }

    MOOD_EMOJI: dict[str, str] = {
        "celebratory": "🎉",
        "love-struck": "😍",
        "adventurous": "🧭",
        "anxious": "😬",
        "sleepy": "😴",
        "mischievous": "🕵️",
        "curious": "🤔",
    }

    async def evaluate(self, agent, ctx, inputs: EvalInputs, output_group) -> EvalResult:
        """Detect mood from message and return emoji representation.

        Args:
            agent: Agent instance
            ctx: Execution context
            inputs: EvalInputs with input artifacts
            output_group: OutputGroup defining what artifacts to produce
        """
        prompt = inputs.first_as(MoodPrompt)
        if not prompt:
            return EvalResult.empty()

        detected, keywords = self._detect_mood(prompt.message)
        emoji = self.MOOD_EMOJI.get(detected, self.MOOD_EMOJI["curious"])

        artifact = MoodEmoji(
            speaker=prompt.speaker,
            detected_mood=detected,
            emoji=emoji,
            explanation=self._explain(prompt.message, detected, keywords),
        )
        return EvalResult.from_object(artifact, agent=agent)

    def _detect_mood(self, message: str) -> tuple[str, list[str]]:
        words = {word.strip(".,!?").lower() for word in message.split()}
        hits: Counter[str] = Counter()

        for mood, keywords in self.MOOD_KEYWORDS.items():
            matched = keywords & words
            if matched:
                hits[mood] += len(matched)

        if not hits:
            return "curious", []

        mood, _score = hits.most_common(1)[0]
        matched_keywords = sorted(self.MOOD_KEYWORDS[mood] & words)
        return mood, matched_keywords

    def _explain(self, message: str, mood: str, keywords: list[str]) -> str:
        if mood == "curious":
            return "No obvious emotional keywords spotted, so we defaulted to curious."
        if keywords:
            terms = ", ".join(keywords)
            return f"We picked up {terms!r} in the message '{message}'."
        return f"We sensed {mood} energy in '{message}'."


async def main() -> None:
    flock = Flock()

    (
        flock.agent("emoji_curator")
        .description("Turns short messages into emoji-coded vibes.")
        .consumes(MoodPrompt)
        .publishes(MoodEmoji)
        .with_engines(EmojiMoodEngine())
    )

    await flock.publish(MoodPrompt(speaker="Ava", message="Just landed my dream promotion!"))
    await flock.publish(MoodPrompt(speaker="Luis", message="Planning a secret quest this weekend."))
    await flock.publish(
        MoodPrompt(speaker="Mina", message="Love is in the air—can't stop smiling!")
    )
    await flock.publish(MoodPrompt(speaker="Noah", message="Yikes, the deadline is tomorrow."))

    await flock.run_until_idle()

    print("\nEmoji Mood Report")
    print("-----------------")
    for artifact in await flock.store.list():
        if artifact.produced_by != "emoji_curator":
            continue
        payload = artifact.payload
        print(
            f"{payload['speaker']:>5}: {payload['emoji']} "
            f"({payload['detected_mood']}) -> {payload['explanation']}"
        )


if __name__ == "__main__":
    asyncio.run(main())

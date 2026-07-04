"""Manual test for Google Cloud TTS."""

import asyncio

from ai.tools.tts import generate_audio


async def main() -> None:
    audio_url = await generate_audio(
        "Welcome to Wandr. This is a quick test of the travel narration audio pipeline.",
        "warm",
    )
    audio_mode = "signed GCS URL" if audio_url.startswith("https://") else "inline data URL"
    print(f"Generated audio mode: {audio_mode}")
    print("Generated audio URL prefix:")
    print(audio_url[:120] + ("..." if len(audio_url) > 120 else ""))


if __name__ == "__main__":
    asyncio.run(main())

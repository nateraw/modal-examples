import io
import os
import tempfile
from pathlib import Path

import modal


app = modal.App(
    "example-dynamic-batching-audio",
    image=modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "libsndfile1")
    .pip_install("soundfile")
    .pip_install("torch", "torchaudio", index_url="https://download.pytorch.org/whl/cpu"),
)


@app.cls()
class AudioReverser:
    @modal.batched(max_batch_size=4, wait_ms=1000)
    async def reverse_audio_batch(self, audio_bytes_list: list[bytes]) -> list[bytes]:
        import torch
        import torchaudio

        reversed_audio_bytes = []

        for audio_bytes in audio_bytes_list:
            # Write bytes to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".opus") as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            try:
                # Load audio
                waveform, sample_rate = torchaudio.load(tmp_path)

                # Reverse the audio (flip along time axis)
                reversed_waveform = torch.flip(waveform, dims=[1])

                # Save to bytes
                buffer = io.BytesIO()
                # Save as wav for compatibility
                torchaudio.save(buffer, reversed_waveform, sample_rate, format="wav")
                reversed_audio_bytes.append(buffer.getvalue())

                print(f"Reversed audio of size {len(audio_bytes)} bytes")

            finally:
                # Clean up temp file
                os.unlink(tmp_path)

        return reversed_audio_bytes


@app.local_entrypoint()
async def main(
    audio_dir: str = "./data/train",
    out_dir: str = "./data/reversed",
    pattern: str = "*.opus",
    limit: int = 37,
):
    audio_reverser = AudioReverser()

    # Find audio files
    audio_dir_path = Path(audio_dir)
    audio_files = list(audio_dir_path.glob(pattern))[:limit]

    if not audio_files:
        print(f"No files matching pattern '{pattern}' found in {audio_dir}")
        return

    print(f"Found {len(audio_files)} audio files to process")

    # Read audio files as bytes
    audio_bytes_list = []
    for audio_file in audio_files:
        print(f"Reading {audio_file}")
        with open(audio_file, "rb") as f:
            audio_bytes_list.append(f.read())

    # Process audio files
    reversed_audio_list = []
    async for reversed_bytes in audio_reverser.reverse_audio_batch.map.aio(audio_bytes_list):
        reversed_audio_list.append(reversed_bytes)

    # Save reversed audio files
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    for i, (original_file, reversed_bytes) in enumerate(zip(audio_files, reversed_audio_list)):
        # Change extension to .wav since we're saving as wav
        save_path = out_path / f"{original_file.stem}.wav"
        with open(save_path, "wb") as f:
            f.write(reversed_bytes)
        print(f"Saved reversed audio to {save_path}")

    print(f"Successfully processed {len(audio_files)} audio files")

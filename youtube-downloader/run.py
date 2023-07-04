import csv
import os
import subprocess
import time
from pathlib import Path

import requests
from modal import Image, Stub


stub = Stub("parallel_test")
stub.image = Image.debian_slim(python_version="3.10").apt_install("ffmpeg").pip_install("yt-dlp", "tqdm", "requests")


@stub.function()
def download_clip(ytid, start_sec, end_sec, output_path="./data/videos", audio_only=False):
    os.makedirs(output_path, exist_ok=True)

    ext = "mp4"
    if audio_only:
        ext = "wav"

    output_filename = os.path.join(output_path, f"{ytid}.{ext}")

    if audio_only:
        cmd = f'''yt-dlp --quiet --no-warnings --force-keyframes-at-cuts -x --audio-format wav -f bestaudio -o "{output_filename}" --download-sections "*{start_sec}-{end_sec}" "https://www.youtube.com/watch?v={ytid}"'''
    else:
        cmd = f'''yt-dlp --quiet --no-warnings --force-keyframes-at-cuts -f mp4 -o "{output_filename}" --download-sections "*{start_sec}-{end_sec}" "https://www.youtube.com/watch?v={ytid}"'''

    subprocess.run(cmd, shell=True)

    if not os.path.exists(output_filename):
        return None

    return f"{ytid}.{ext}", open(output_filename, "rb").read()


@stub.local_entrypoint()
def main(limit: int = 128, out_dir: str = "./audio"):

    annotation_url = "https://huggingface.co/datasets/google/MusicCaps/resolve/main/musiccaps-public.csv"
    anno_filepath = Path("musiccaps-public.csv")
    out_dir = Path(out_dir)
    out_dir.mkdir(exist_ok=True, parents=True)
    if not anno_filepath.exists():
        print("Downloading annotations...")
        r = requests.get(annotation_url)
        anno_filepath.write_text(r.text)

    with anno_filepath.open() as f:
        # read with first row being headers
        reader = csv.DictReader(f)
        # convert to list of tuples
        data_in = [
            (row["ytid"], int(row["start_s"]), int(row["end_s"]))
            for row in reader
            if not Path(out_dir / f"{row['ytid']}.wav").exists()
        ]

    start_time = time.time()
    n_examples = limit or len(data_in)
    data_in = data_in[:n_examples]
    print(f"Downloading {n_examples} clips")

    for i, result in enumerate(
        download_clip.starmap(
            data_in,
            order_outputs=False,
            return_exceptions=True,
            kwargs={"output_path": str(out_dir), "audio_only": True},
        )
    ):
        if not isinstance(result, tuple):
            print(f"{i + 1}/{n_examples} - 🚨 Error")
            continue

        name, data = result
        file_outpath = out_dir / name
        file_outpath.write_bytes(data)
        print(f"{i + 1}/{n_examples} - ✅ Success")

    end_time = time.time()
    print(f"Time taken: {end_time - start_time} seconds")

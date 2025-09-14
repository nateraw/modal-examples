Get some example audios

```bash
HF_HUB_ENABLE_HF_TRANSFER=1 huggingface-cli download rkstgr/mtg-jamendo data/train/0.tar --local-dir . --repo-type dataset && \
tar -xf data/train/0.tar -C data/train/ && \
rm data/train/0.tar
```

Run:

```bash
modal run dynamic-batching-audio/app.py
```
# YouTube Downloader

This example downloads the MusicCaps dataset from YouTube. It calls the download function in parallel by using Modal's starmap function, generating results as they become available on the various machines.

TODO - benchmark against local download/parallel download. Quick check using [this](https://github.com/nateraw/download-musiccaps-dataset) showed a local run to download 32 videos took 1:20, while the modal run took around 20 seconds when limited to 32 videos.

## Usage

See readme in the parent directory for instructions on how to install the modal-client + authenticate. 

Then...from this directory, you can run the following to download the videos:

```
modal run run.py
```

Provide arguments to change the output dir or limit the number of videos to download:

```
modal run run.py --limit 16 --out-dir ./data_dir
```
# modal-examples

Playing around with [modal](https://modal.com).

## Getting Started

Install modal client and authenticate:

```
pip install modal-client
modal token new
```


## Examples

<!-- Table below -->

| Example | Description |
| --- | --- |
| [QR Code Stable Diffusion](./qrcode-stable-diffusion) | Generate stylish QR Codes with Stable Diffusion on modal. |
| [YouTube Downloader](./youtube-downloader) | This example downloads the MusicCaps dataset from YouTube. It calls the download function in parallel by using Modal's starmap function, generating results as they become available on the various machines. |
| [Lambda Cloud Watcher](./lambda_watcher) | Text yourself whenever the machine you want on [Lambda](https://lambdalabs.com/cloud) is available. |

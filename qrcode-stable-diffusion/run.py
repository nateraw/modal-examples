import io
import time
from pathlib import Path

from modal import Image, Stub, method


stub = Stub("stable-diffusion-qrcode-cli")
cache_dir = "/vol/cache"


def download_model():
    import tempfile

    import diffusers
    import torch

    with tempfile.TemporaryDirectory() as temp_dir:
        controlnet = diffusers.ControlNetModel.from_pretrained(
            "DionTimmer/controlnet_qrcode-control_v1p_sd15", torch_dtype=torch.float16, cache_dir=temp_dir
        )
        pipe = diffusers.StableDiffusionControlNetImg2ImgPipeline.from_pretrained(
            "runwayml/stable-diffusion-v1-5",
            controlnet=controlnet,
            safety_checker=None,
            torch_dtype=torch.float16,
            cache_dir=temp_dir,
        )
        pipe.scheduler = diffusers.DPMSolverMultistepScheduler.from_config(
            pipe.scheduler.config, use_karras=True, algorithm_type="sde-dpmsolver++", cache_dir=temp_dir
        )
        pipe.save_pretrained(cache_dir, safe_serialization=True)


image = (
    Image.debian_slim(python_version="3.10")
    .pip_install(
        "torch==2.0.1+cu117",
        find_links="https://download.pytorch.org/whl/torch_stable.html",
    )
    .pip_install(
        "diffusers",
        "transformers",
        "accelerate",
        "xformers",
        "Pillow",
        "qrcode",
    )
    .run_function(download_model)
)
stub.image = image


def resize_for_condition_image(input_image, resolution: int):
    from PIL.Image import LANCZOS

    input_image = input_image.convert("RGB")
    W, H = input_image.size
    k = float(resolution) / min(H, W)
    H *= k
    W *= k
    H = int(round(H / 64.0)) * 64
    W = int(round(W / 64.0)) * 64
    img = input_image.resize((W, H), resample=LANCZOS)
    return img


@stub.cls(gpu="A10G")
class StableDiffusion:
    def __enter__(self):
        import diffusers
        import torch

        torch.backends.cuda.matmul.allow_tf32 = True
        self.pipe = diffusers.StableDiffusionControlNetImg2ImgPipeline.from_pretrained(
            cache_dir, torch_dtype=torch.float16
        ).to("cuda")
        self.pipe.enable_xformers_memory_efficient_attention()

    def generate_qrcode(self, qr_code_content):
        import qrcode

        print("Generating QR Code from content")
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_code_content)
        qr.make(fit=True)

        qrcode_image = qr.make_image(fill_color="black", back_color="white")
        qrcode_image = resize_for_condition_image(qrcode_image, 768)
        return qrcode_image

    @method()
    def run_inference(
        self,
        prompt: str,
        qr_code_content: str,
        num_inference_steps: int = 30,
        negative_prompt: str = None,
        guidance_scale: float = 7.5,
        controlnet_conditioning_scale: float = 1.5,  # 1.3, 1.11, 1.5
        strength: float = 0.9,  # 0.8
        seed: int = -1,
        num_images_per_prompt: int = 1,
    ) -> list[bytes]:
        import torch

        seed = torch.randint(0, 2**32, (1,)).item() if seed == -1 else seed
        qrcode_image = self.generate_qrcode(qr_code_content)
        out = self.pipe(
            prompt=[prompt] * num_images_per_prompt,
            negative_prompt=[negative_prompt] * num_images_per_prompt,
            image=[qrcode_image] * num_images_per_prompt,
            control_image=[qrcode_image] * num_images_per_prompt,
            width=768,
            height=768,
            guidance_scale=float(guidance_scale),
            controlnet_conditioning_scale=float(controlnet_conditioning_scale),
            generator=torch.Generator().manual_seed(seed),
            strength=float(strength),
            num_inference_steps=num_inference_steps,
        )
        # Convert to PNG bytes
        image_output = []
        for image in out.images:
            with io.BytesIO() as buf:
                image.save(buf, format="PNG")
                image_output.append(buf.getvalue())
        return image_output


@stub.local_entrypoint()
def entrypoint(
    prompt: str,
    qrcode_content: str,
    negative_prompt: str = "ugly, disfigured, low quality, blurry, nsfw",
    steps: int = 40,
    samples: int = 1,
    guidance_scale: float = 7.5,
    controlnet_conditioning_scale: float = 1.5,  # 1.3, 1.11, 1.5
    strength: float = 0.9,  # 0.8
    seed: int = -1,
):
    """Local entrypoint that you can use from the CLI to generate QR Code images via a Modal app.
    Example:
        modal run run.py \
            --prompt "ramen noodle soup, animated by studio ghibli, vivid colors" \
            --qrcode-content "https://modal.com" \
            --samples 4 \
            --steps 40
    Args:
        prompt (str):
            A text prompt to generate the QR Code image.
        qrcode_content (str):
            The URL or content to encode in the QR Code.
        negative_prompt (str, optional):
            Negative prompts to use when generating the image.
            Defaults to "ugly, disfigured, low quality, blurry, nsfw".
        steps (int, optional):
            Number of inference steps in diffusion process. Defaults to 40.
        samples (int, optional):
            Number of images to generate. Defaults to 1.
        guidance_scale (float, optional):
            Guidance scale as defined in [Classifier-Free Diffusion Guidance](https://arxiv.org/abs/2207.12598).
            Defaults to 7.5.
        controlnet_conditioning_scale (float, optional):
            The outputs of the controlnet are multiplied by `controlnet_conditioning_scale` before they are added
            to the residual in the original unet. If multiple ControlNets are specified in init, you can set the
            corresponding scale as a list. Defaults to 1.5.
        strength (float, optional):
            Conceptually, indicates how much to transform the masked portion of the reference image. Must be
            between 0 and 1. Defaults to 0.9.
        seed (int, optional):
            Random seed to enforce reproducibility. If set to -1, we pick a random number as the seed. Defaults to -1.
    """

    print(f"prompt => {prompt}, qrcode_content => {qrcode_content}, steps => {steps}, samples => {samples}")

    dir = Path("./qr_code_output")
    if not dir.exists():
        dir.mkdir(exist_ok=True, parents=True)

    sd = StableDiffusion()
    t0 = time.time()
    images = sd.run_inference.call(
        prompt,
        qrcode_content,
        num_inference_steps=steps,
        num_images_per_prompt=samples,
        negative_prompt=negative_prompt,
        guidance_scale=guidance_scale,
        controlnet_conditioning_scale=controlnet_conditioning_scale,
        strength=strength,
        seed=seed,
    )
    total_time = time.time() - t0
    print(f"Took {total_time:.3f}s ({(total_time)/len(images):.3f}s / image).")
    for j, image_bytes in enumerate(images):
        output_path = dir / f"output_{j}.png"
        print(f"Saving it to {output_path}")
        with open(output_path, "wb") as f:
            f.write(image_bytes)

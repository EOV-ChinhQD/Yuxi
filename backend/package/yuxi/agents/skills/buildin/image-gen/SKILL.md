---
name: image-gen
description: "Generate images in the Agent sandbox and save them to outputs. Use this skill when the user requires the generation of images, posters, illustrations, and illustrations, or specifies Qwen-Image or other compatible image generation interfaces."
---

# Image generation skills

Use this skill to organize the image generation process when the user requests to generate pictures, posters, illustrations, drawings, or explicitly mentions Qwen-Image.

## Default generated interface

SiliconFlow's Qwen-Image interface is used by default:

- Endpoint: `POST https://api.siliconflow.cn/v1/images/generations`
- Model: `Qwen/Qwen-Image`
-Default parameters:
  - `negative_prompt`: `""`
  - `num_inference_steps`: `20`
  - `guidance_scale`: `7.5`

When calling an external interface, `SILICONFLOW_API_KEY` must be read in the Agent sandbox execution environment. Do not rely on backend process environment variables.

## Operation process

1. Clarify the image content, style, size or constraints that the user wants to generate; when the information is insufficient but does not affect the generation, use reasonable default values ​​and do not ask repeatedly.
2. Use the available execution tools to run the script in the sandbox, call the image generation interface, pass in the `prompt` compiled according to user requirements, and pass in `negative_prompt`, `num_inference_steps`, and `guidance_scale` as needed.
3. Read the image address from the generated interface response. The default path is `images[0].url`.
4. Use `Authorization: Bearer $SILICONFLOW_API_KEY` in the same sandbox script to download the image address; if the interface directly returns base64, it will be decoded and saved directly.
5. Save the final image to `/home/gem/user-data/outputs/`, for example `/home/gem/user-data/outputs/generated-image.png`.
6. Call `present_artifacts`, pass in the saved outputs virtual path, and let the front end display the image products.
7. The final reply briefly states that the image has been generated, and do not display the external temporary URL as the final result.

## Script example

The prompt and output file name can be adjusted according to user needs:

```python
import os
import requests
from pathlib import Path

api_key = os.environ["SILICONFLOW_API_KEY"]
prompt = "Picture prompt words organized according to user needs"

response = requests.post(
    "https://api.siliconflow.cn/v1/images/generations",
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    json={
        "model": "Qwen/Qwen-Image",
        "prompt": prompt,
        "negative_prompt": "",
        "num_inference_steps": 20,
        "guidance_scale": 7.5,
    },
    timeout=120,
)
response.raise_for_status()
image_url = response.json()["images"][0]["url"]

image_response = requests.get(
    image_url,
    headers={"Authorization": f"Bearer {api_key}"},
    timeout=120,
)
image_response.raise_for_status()

output_path = Path("/home/gem/user-data/outputs/generated-image.png")
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_bytes(image_response.content)
print(output_path.as_posix())
```

##Multi-model extension

If the user specifies another image generation model or compatible interface, the image can be generated first according to the protocol of that interface. As long as you finally get the image bytes or base64, save it to `/home/gem/user-data/outputs/`, and then call `present_artifacts` to display it.

## Key constraints

- Do not treat the temporary URL returned by the external generation interface as the final result and display it directly to the user.
- Do not call the backend MinIO upload tool; image generation and downloading should be done within the sandbox.
- If `SILICONFLOW_API_KEY` is missing, the user should be explicitly prompted to configure it in the Agent sandbox environment variable.
- `present_artifacts` must be called after saving to outputs, otherwise the front end will not automatically display the generated image.

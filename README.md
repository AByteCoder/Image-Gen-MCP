# Image Gen MCP

A FastMCP stdio server that generates and edits images using the Google Gemini image model.

## Files

| File | Purpose |
|---|---|
| `image_gen_mcp.py` | The MCP server |
| `pyproject.toml` | Package metadata and entry point |
| `requirements.txt` | Python dependencies |

## Setup

### 1. Install

**As a package (recommended):**

```bash
pip install /path/to/image-gen-mcp
```

Or in editable mode for development:

```bash
pip install -e /path/to/image-gen-mcp
```

**From requirements only:**

```bash
pip install -r requirements.txt
```

### 2. Obtain credentials

**Option A — Gemini API key**

1. Go to [Google AI Studio](https://ai.google.dev/gemini-api/docs/api-key) and sign in.
2. Click **Get a Gemini API key** and create a new key (or copy an existing one).
3. Store the key somewhere safe; you will pass it as `GEMINI_API_KEY`.

**Option B — Google service account (Vertex AI)**

1. In the [Google Cloud Console](https://docs.cloud.google.com/iam/docs/service-accounts-create), open the project you want to use and enable the **Vertex AI API**.
2. Navigate to **IAM & Admin → Service Accounts** and click **Create service account**.
3. Fill in a name, then on the **Grant access** step assign the **Vertex AI User** role (`roles/aiplatform.user`).
4. After creating the account, open it, go to the **Keys** tab, click **Add Key → Create new key**, and choose **JSON**.
5. Download the JSON file; you will pass its path as `GOOGLE_SERVICE_ACCOUNT_FILE`.

---

### 3. Set environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | Yes (or service account) | — | Your Google Gemini API key |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Yes (or API key) | — | Path to a Google service account JSON key file (alternative to API key) |
| `GOOGLE_VERTEX_LOCATION` | No | `global` | Vertex AI location; only used when authenticating via service account |
| `IMAGE_OUTPUT_DIR` | No | `./images` | Directory where generated/edited images are saved |
| `IMAGE_MODEL` | No | `gemini-3.1-flash-image-preview` | Gemini model to use for image generation |
| `RETURN_FILEPATH` | No | — | Set to `1` or `true` to return file paths instead of inline image content |

Either `GEMINI_API_KEY` or `GOOGLE_SERVICE_ACCOUNT_FILE` must be set; the server will raise an error on startup if neither is present.

**API key auth:**

```bash
export GEMINI_API_KEY=your_api_key_here
export IMAGE_OUTPUT_DIR=/path/to/your/images   # optional
```

**Service account auth (Vertex AI):**

```bash
export GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/service_account_key.json
export GOOGLE_VERTEX_LOCATION=us-central1      # optional, defaults to global
```

### 4. Run the server

If installed as a package:

```bash
image-gen-mcp
```

Or directly:

```bash
python image_gen_mcp.py
```

## Register with an MCP host

Add the following to your MCP host config (e.g. Claude Desktop `config.json`):

```json
{
  "mcpServers": {
    "image-gen-mcp": {
      "command": "image-gen-mcp",
      "env": {
        "GEMINI_API_KEY": "your_api_key_here",
        "GOOGLE_SERVICE_ACCOUNT_FILE": "/path/to/service_account_key.json",
        "IMAGE_OUTPUT_DIR": "/path/to/your/images"
      }
    }
  }
}
```

## Tools

### `generate_image`

Generate a new image from a text prompt.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `prompt` | string | Yes | — | Text description of the image to generate |
| `filename_prefix` | string | No | `generated` | Prefix for the saved filename |
| `aspect_ratio` | string | No | — | Output aspect ratio (see values below) |
| `resolution` | string | No | `1K` | Output resolution: `512px`, `1K`, `2K`, `4K` |

---

### `edit_image`

Edit one or more existing images using a text prompt.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `image_path` | list[string] | Yes | — | Absolute file paths or HTTP(S) URLs to the source image(s) |
| `prompt` | string | Yes | — | Text description of the desired edits |
| `filename_prefix` | string | No | `edited` | Prefix for the saved filename |
| `aspect_ratio` | string | No | — | Output aspect ratio (see values below) |
| `resolution` | string | No | `1K` | Output resolution: `512px`, `1K`, `2K`, `4K` |

---

### Aspect ratio values

`1:1`, `1:4`, `1:8`, `2:3`, `3:2`, `3:4`, `4:1`, `4:3`, `4:5`, `5:4`, `8:1`, `9:16`, `16:9`, `21:9`

---

## Notes

- Images are saved as PNG with a timestamp suffix, e.g. `generated_20260307_143022.png`.
- The model defaults to `gemini-3.1-flash-image-preview`. Override it with the `IMAGE_MODEL` env variable.
- When `RETURN_FILEPATH` is set, tools return the file path and a `resource_id` (e.g. `images://generated_20260307_143022`) that can be used to fetch the image via the MCP resource endpoint.
- Multiple images passed to `edit_image` are composited or used as references within a single generation request.

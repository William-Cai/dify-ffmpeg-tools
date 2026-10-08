## FFmpeg Tools

**Author:** william-cai  
**Version:** 0.0.1  
**Type:** tool

### Description

FFmpeg Tools is a Dify plugin that provides powerful media processing capabilities powered by FFmpeg. Currently, it includes video concatenation functionality, with more tools to be added in the future.

This plugin allows AI agents and workflows in Dify to process video content programmatically, enabling use cases such as:

- Merging multiple video clips into a single seamless video
- Creating video compilations from multiple sources
- Automating video post-processing tasks

### Features

#### Video Concatenation

Merge multiple video URLs into a single video file. The tool accepts a list of video URLs and combines them in order into one output video.

**Use cases:**
- Combine multiple video segments into a complete video
- Create video montages from clips
- Stitch together recorded sessions or streams

### Setup

#### Prerequisites

1. **FFmpeg**: This plugin requires FFmpeg to be installed on the system where the plugin runs.
   - For Dify Cloud: FFmpeg is pre-installed and ready to use.
   - For self-hosted Dify: Ensure FFmpeg is installed and available in the system PATH.

2. **Dify**: This plugin requires Dify version 0.0.1 or higher.

#### Installation

Install the plugin from the Dify Marketplace:

1. Go to your Dify workspace
2. Navigate to **Plugins** in the workspace settings
3. Search for "FFmpeg Tools" in the marketplace
4. Click **Install**

Alternatively, you can install from GitHub:

1. Clone this repository
2. Package the plugin using the Dify CLI
3. Upload the `.difypkg` file to your Dify instance

### Usage

#### Video Concatenation Tool

The video concatenation tool merges multiple videos into one.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `video_urls` | string (JSON array) | Yes | A JSON array of video URLs to merge, in order. Example: `["https://example.com/video1.mp4", "https://example.com/video2.mp4"]` |
| `output_name` | string | No | Output file name without extension. Default: `merged_video` |

**Example:**

In a Dify workflow or chatflow, you can invoke the tool with:

```json
{
  "video_urls": "[\"https://example.com/intro.mp4\", \"https://example.com/main.mp4\", \"https://example.com/outro.mp4\"]",
  "output_name": "final_video"
}
```

The tool will return a merged video file that can be used in subsequent workflow steps or presented to the user.

### Limitations

- All input videos should have compatible formats (codec, resolution, frame rate) for seamless concatenation. Mismatched formats may result in playback issues.
- The tool processes videos sequentially, so very long videos or many videos may take significant processing time.
- Input videos must be accessible via URL (public URLs or URLs accessible by the Dify server).

### Future Plans

More FFmpeg-based tools are planned for future releases, including:

- Video format conversion
- Video trimming and cutting
- Audio extraction from video
- Video compression and optimization
- Thumbnail generation

Contributions and feature requests are welcome!

### License

This plugin is open-source. See the repository for license details.

### Support

For issues, feature requests, or contributions, please visit the [GitHub repository](https://github.com/William-Cai/ffmpeg-tools-plugin).

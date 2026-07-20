"""Single source of app credit/metadata.

Used by the CLI now and ``GET /api/about`` in a later milestone. Keep this in
sync with ``docs/`` and the in-app credits page/footer.
"""

from __future__ import annotations

APP_NAME = "AI DeepResearch AutoFlow"
VERSION = "0.1.0"
LICENSE = "MIT"
AUTHORS = [
    {"name": "Narenrit Hadsadintorn", "handle": "captainkie", "role": "Author"},
    {"name": "Claude (Anthropic)", "handle": "anthropic", "role": "AI pair-builder"},
]
ACKNOWLEDGEMENTS = [
    {
        "name": "open_deep_research",
        "url": "https://github.com/langchain-ai/open_deep_research",
        "license": "MIT",
    },
    {
        "name": "deer-flow",
        "url": "https://github.com/bytedance/deer-flow",
        "license": "MIT",
    },
    {
        "name": "DeepResearch",
        "url": "https://github.com/Alibaba-NLP/DeepResearch",
        "license": "Apache-2.0",
    },
    {
        "name": "autoresearch",
        "url": "https://github.com/karpathy/autoresearch",
        "license": "MIT",
    },
]

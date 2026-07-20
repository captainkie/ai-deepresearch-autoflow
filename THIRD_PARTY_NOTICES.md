# Third-Party Notices & Acknowledgements

AI DeepResearch AutoFlow was designed by studying several excellent open-source
deep-research projects. We wrote our own original code, inspired by their **architecture and
patterns** — no source files were copied verbatim. We gratefully acknowledge and credit them:

| Project | Author | License | What inspired us |
|---|---|---|---|
| [DeepResearch](https://github.com/Alibaba-NLP/DeepResearch) | Alibaba-NLP (Tongyi) | Apache-2.0 | ReAct tool loop; goal-directed page summarization ("fetch → summarize against a goal") |
| [open_deep_research](https://github.com/langchain-ai/open_deep_research) | LangChain | MIT | Core research architecture: plan → supervisor/researcher → compress → synthesize; report structure; provider-agnostic model config |
| [deer-flow](https://github.com/bytedance/deer-flow) | ByteDance | MIT | Product UX: live SSE streaming, human-in-the-loop plan review, Next.js + Python split |
| [autoresearch](https://github.com/karpathy/autoresearch) | Andrej Karpathy | MIT | Minimal, hackable, from-scratch engineering ethos |

## License texts

The above projects are distributed under the MIT and Apache-2.0 licenses. Full license texts
are available in each project's repository (linked above). Apache-2.0 (DeepResearch) requires
that its `NOTICE`/attribution be preserved when its code is used; as we do not redistribute
their source, this acknowledgement satisfies attribution for the ideas we drew on.

This project itself is released under the MIT License — see [LICENSE](./LICENSE).

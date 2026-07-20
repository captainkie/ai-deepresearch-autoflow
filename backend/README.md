# AutoFlow Research — Backend

Provider-agnostic async deep-research engine. See the full quickstart in Milestone 1
(this file is expanded in Task 15).

```bash
uv sync --extra dev
uv run pytest -q
uv run autoflow research "Analyze competitor brand: ExampleCo" --lang en \
  --llm mock --search mock --crawl mock
```

from __future__ import annotations

from app.core.sources import SourceRegistry
from app.models.schemas import Source


async def test_add_increments_from_one():
    reg = SourceRegistry()
    a = await reg.add(url="https://a", title="A")
    b = await reg.add(url="https://b", title="B")
    assert isinstance(a, Source)
    assert a.id == 1
    assert b.id == 2


async def test_dedup_same_url_returns_same_id():
    reg = SourceRegistry()
    first = await reg.add(url="https://a", title="A")
    dup = await reg.add(url="https://a", title="A again")
    assert dup.id == first.id
    assert len(reg.all()) == 1


async def test_all_in_id_order():
    reg = SourceRegistry()
    for url in ("https://a", "https://b", "https://c"):
        await reg.add(url=url, title=url)
    assert [s.id for s in reg.all()] == [1, 2, 3]
    assert len(reg) == 3

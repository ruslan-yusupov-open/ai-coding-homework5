import asyncio

from validate import validate


def test_real_stdio_protocol(tmp_path):
    report = asyncio.run(validate(tmp_path / "evidence"))
    assert len(report["checks"]) == 8

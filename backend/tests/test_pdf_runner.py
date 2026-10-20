import asyncio
import stat
from pathlib import Path

import pytest

from app.pdf import runner
from app.pdf.errors import PdfEngineError

FAKE = """#!/bin/sh
outdir=""
prev=""
for arg in "$@"; do
  if [ "$prev" = "--outdir" ]; then outdir="$arg"; fi
  prev="$arg"
done
case "$FAKE_MODE" in
  ok) printf '%%PDF-1.7 fake' > "$outdir/invoice.pdf" ;;
  fail) echo "boom" >&2; exit 1 ;;
  nofile) exit 0 ;;
  sleep) sleep 30 ;;
  version) echo "LibreOffice fake" ;;
esac
"""


@pytest.fixture
def fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    script = tmp_path / "soffice"
    script.write_text(FAKE)
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    monkeypatch.setattr(runner, "soffice_path", lambda: str(script))
    monkeypatch.setattr(runner, "PROFILE_ROOT", tmp_path / "lo")
    monkeypatch.setattr("tempfile.tempdir", str(scratch))

    def mode(name: str) -> None:
        monkeypatch.setenv("FAKE_MODE", name)

    mode.scratch = scratch  # type: ignore[attr-defined]
    mode.profiles = tmp_path / "lo"  # type: ignore[attr-defined]
    return mode


def _leftovers(fake) -> list[Path]:
    return list(fake.scratch.glob("ifrit-pdf-*"))


async def test_a_conversion_returns_the_pdf_and_removes_its_scratch_directory(
    fake,
) -> None:
    fake("ok")
    assert await runner.convert_to_pdf(b"odt") == b"%PDF-1.7 fake"
    assert _leftovers(fake) == []


async def test_the_scratch_directory_is_private(
    fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake("ok")
    seen: list[int] = []
    real = runner.asyncio.create_subprocess_exec

    async def spy(*args, **kwargs):
        directory = next(fake.scratch.glob("ifrit-pdf-*"))
        seen.append(stat.S_IMODE(directory.stat().st_mode))
        return await real(*args, **kwargs)

    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", spy)
    await runner.convert_to_pdf(b"odt")
    assert seen == [0o700]


async def test_profiles_are_seeded_with_macros_disabled(fake) -> None:
    fake("ok")
    await runner.convert_to_pdf(b"odt")
    settings = next(fake.profiles.glob("profile-*/user/registrymodifications.xcu"))
    text = settings.read_text()
    assert "MacroSecurityLevel" in text and "DisableMacrosExecution" in text


async def test_a_failing_conversion_raises_and_cleans_up(
    fake, caplog: pytest.LogCaptureFixture
) -> None:
    fake("fail")
    with pytest.raises(PdfEngineError) as raised:
        await runner.convert_to_pdf(b"odt")
    assert "boom" not in str(raised.value)
    assert "boom" in caplog.text
    assert _leftovers(fake) == []


async def test_a_conversion_that_leaves_no_file_raises(fake) -> None:
    fake("nofile")
    with pytest.raises(PdfEngineError):
        await runner.convert_to_pdf(b"odt")
    assert _leftovers(fake) == []


async def test_a_conversion_past_the_limit_is_stopped(
    fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake("sleep")
    monkeypatch.setattr(runner, "TIMEOUT_SECONDS", 1)
    with pytest.raises(PdfEngineError, match="too long"):
        await runner.convert_to_pdf(b"odt")
    assert _leftovers(fake) == []
    # The slot came back: the next conversion is not stuck behind the stopped one.
    fake("ok")
    assert await runner.convert_to_pdf(b"odt") == b"%PDF-1.7 fake"


async def test_a_missing_converter_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "soffice_path", lambda: None)
    with pytest.raises(PdfEngineError):
        await runner.convert_to_pdf(b"odt")


async def test_conversions_never_exceed_the_slots(
    fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake("ok")
    running = 0
    peak = 0
    real = runner.asyncio.create_subprocess_exec

    async def counting(*args, **kwargs):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.05)
        try:
            return await real(*args, **kwargs)
        finally:
            running -= 1

    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", counting)
    await asyncio.gather(*(runner.convert_to_pdf(b"odt") for _ in range(6)))
    assert peak <= runner.SLOTS


async def test_the_start_up_check_warns_without_the_converter(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(runner, "soffice_path", lambda: None)
    assert await runner.check_engine() is False
    assert "not installed" in caplog.text


async def test_the_start_up_check_passes_with_a_working_converter(fake) -> None:
    fake("version")
    assert await runner.check_engine() is True

"""Converts a filled ODT file to PDF with a headless LibreOffice.

LibreOffice allows one process per user profile and starts slowly with a fresh one, so a small
fixed number of profile directories are kept and each conversion takes whichever is free; that
also caps how many conversions run at once, and so the memory they use."""

import asyncio
import contextlib
import logging
import os
import shutil
import signal
import tempfile
import weakref
from collections.abc import AsyncIterator
from pathlib import Path

from app.pdf.errors import PdfEngineError

logger = logging.getLogger(__name__)

SLOTS = 2
TIMEOUT_SECONDS = 60
VERSION_TIMEOUT_SECONDS = 5
# Where the profiles live, next to the scratch directories: all under the system temporary
# folder, which the container clears on restart.
PROFILE_ROOT = Path(tempfile.gettempdir()) / "ifrit-lo"

# Macros off at the strictest level and no prompt about updating links, set in each profile
# before its first start so a document can never run code or fetch anything on its own.
_PROFILE_SETTINGS = """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="DisableMacrosExecution" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.openoffice.Office.Writer/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>2</value></prop></item>
</oor:items>
"""

_queues: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Queue[int]] = (
    weakref.WeakKeyDictionary()
)


def soffice_path() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def _slot_queue() -> asyncio.Queue[int]:
    # One queue per event loop: a queue binds to the loop that first waits on it.
    loop = asyncio.get_running_loop()
    queue = _queues.get(loop)
    if queue is None:
        queue = asyncio.Queue()
        for slot in range(SLOTS):
            queue.put_nowait(slot)
        _queues[loop] = queue
    return queue


@contextlib.asynccontextmanager
async def _slot() -> AsyncIterator[Path]:
    queue = _slot_queue()
    slot = await queue.get()
    try:
        profile = PROFILE_ROOT / f"profile-{slot}"
        await asyncio.to_thread(_seed_profile, profile)
        yield profile
    finally:
        queue.put_nowait(slot)


def _seed_profile(profile: Path) -> None:
    settings = profile / "user" / "registrymodifications.xcu"
    if settings.exists():
        return
    PROFILE_ROOT.mkdir(mode=0o700, exist_ok=True)
    settings.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    settings.write_text(_PROFILE_SETTINGS, encoding="utf-8")


async def _kill(process: asyncio.subprocess.Process) -> None:
    # The converter starts helper processes of its own, so the whole group goes.
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(process.pid, signal.SIGKILL)
    with contextlib.suppress(ProcessLookupError):
        process.kill()
    await process.wait()


async def convert_to_pdf(odt: bytes) -> bytes:
    """The PDF of an ODT file. Raises PdfEngineError for anything that stops it from
    producing one; the cause is logged and never carried in the error."""
    binary = soffice_path()
    if binary is None:
        logger.error("LibreOffice is not installed: cannot make an invoice PDF")
        raise PdfEngineError("The PDF engine is not available")

    # mkdtemp creates the directory with mode 0700: the file written in it is not readable
    # by other users of the machine.
    scratch = Path(await asyncio.to_thread(tempfile.mkdtemp, prefix="ifrit-pdf-"))
    try:
        source = scratch / "invoice.odt"
        await asyncio.to_thread(source.write_bytes, odt)
        async with _slot() as profile:
            process = await asyncio.create_subprocess_exec(
                binary,
                "--headless",
                "--norestore",
                "--nolockcheck",
                "--nodefault",
                "--nologo",
                f"-env:UserInstallation={profile.as_uri()}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(scratch),
                str(source),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            try:
                _, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=TIMEOUT_SECONDS
                )
            except TimeoutError:
                await _kill(process)
                logger.error(
                    "LibreOffice took more than %s s and was stopped", TIMEOUT_SECONDS
                )
                raise PdfEngineError("The PDF engine took too long") from None
            except BaseException:
                await _kill(process)
                raise
        result = scratch / "invoice.pdf"
        if process.returncode != 0 or not await asyncio.to_thread(result.is_file):
            logger.error(
                "LibreOffice failed (exit %s): %s",
                process.returncode,
                stderr.decode("utf-8", "replace")[:2000],
            )
            raise PdfEngineError("The PDF engine could not make the PDF")
        return await asyncio.to_thread(result.read_bytes)
    finally:
        await asyncio.to_thread(shutil.rmtree, scratch, True)


async def check_engine() -> bool:
    """Logs a warning when the converter cannot be started. Never raises: the application
    runs without it, and only the PDF features answer 503."""
    binary = soffice_path()
    if binary is None:
        logger.warning(
            "LibreOffice is not installed: invoice PDFs will not be available"
        )
        return False
    try:
        process = await asyncio.create_subprocess_exec(
            binary,
            "--version",
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        try:
            await asyncio.wait_for(
                process.communicate(), timeout=VERSION_TIMEOUT_SECONDS
            )
        except TimeoutError:
            await _kill(process)
            logger.warning(
                "LibreOffice did not answer --version: invoice PDFs may fail"
            )
            return False
    except OSError:
        logger.warning(
            "LibreOffice could not be started: invoice PDFs will not be available"
        )
        return False
    if process.returncode != 0:
        logger.warning("LibreOffice --version failed: invoice PDFs may fail")
        return False
    return True

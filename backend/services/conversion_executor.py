from __future__ import annotations

import asyncio
import inspect
import multiprocessing
import threading

from backend.config import settings

_slots = threading.BoundedSemaphore(2)


def _worker(sender, converter_id: str, sources: list[bytes], filename: str, options: dict[str, object]) -> None:
    from backend.converters.builtins import converter_registry

    try:
        converter = converter_registry.require(converter_id)
        if converter.convert_batch:
            output = converter.convert_batch(sources)
        elif converter.convert_with_options:
            output = converter.convert_with_options(sources[0], options)
        else:
            output = converter.convert(sources[0], filename)
        if inspect.isawaitable(output): output = asyncio.run(output)
        size = len(output) if isinstance(output, bytes) else len(str(output.get("bundle", ""))) * 3 // 4
        if size > settings.max_output_size_mb * 1024 * 1024:
            raise ValueError("The converted output exceeds the safe output size limit.")
        sender.send((True, output))
    except ValueError as exc:
        sender.send((False, str(exc)))
    except Exception:
        sender.send((False, "The document could not be converted. It may contain unsupported or corrupted content."))
    finally:
        sender.close()


def execute_conversion(converter_id: str, sources: list[bytes], filename: str, options: dict[str, object] | None = None, timeout_seconds: float | None = None):
    timeout = timeout_seconds if timeout_seconds is not None else settings.conversion_timeout_seconds
    if not _slots.acquire(timeout=min(timeout, 10)):
        raise ValueError("The conversion service is busy. Please try again shortly.")
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_worker, args=(sender, converter_id, sources, filename, options or {}), daemon=True)
    try:
        process.start(); sender.close()
        if not receiver.poll(timeout): raise TimeoutError("Conversion exceeded the processing time limit.")
        try:
            success, output = receiver.recv()
        except EOFError as exc:
            raise ValueError("The document processor stopped unexpectedly. Try a smaller file.") from exc
        if not success: raise ValueError(output)
        return output
    finally:
        if process.pid:
            if process.is_alive(): process.terminate()
            process.join(timeout=5)
        receiver.close(); sender.close(); _slots.release()

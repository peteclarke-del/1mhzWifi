#!/usr/bin/env python3
"""Inspect the exact byte and chunk layout presented to Pi1MHz WiCFS."""

from __future__ import annotations

import argparse
import gzip
import io
import json
import struct
import sys
import zipfile
from pathlib import Path
from typing import Any


MAGIC = b"UEF File!\0"
HEADER_SIZE = 12
DATA_CHUNKS = {0x0100, 0x0102, 0x0104}
CHUNK_NAMES = {
    0x0000: "origin information",
    0x0005: "target platform",
    0x0100: "implicit start/stop-bit data",
    0x0101: "multiplexed data",
    0x0102: "explicit tape data",
    0x0104: "defined tape data",
    0x0110: "carrier tone",
    0x0111: "carrier tone with dummy byte",
    0x0112: "integer gap",
    0x0113: "floating-point gap",
    0x0114: "security cycles",
    0x0116: "floating-point baud rate",
}


class UefError(ValueError):
    """A malformed or unsupported UEF container."""


def tape_crc(data: bytes) -> int:
    """Return the Acorn cassette CRC-16 used by standard tape blocks."""
    crc = 0
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 \
                else (crc << 1) & 0xFFFF
    return crc


def inspect_cfs_block(payload: bytes, chunk_index: int,
                      chunk_offset: int) -> dict[str, Any] | None:
    """Decode one standard Acorn cassette block held in an &0100 chunk."""
    if not payload.startswith(b"*"):
        return None
    try:
        name_end = payload.index(0, 1, 12)
    except ValueError:
        return None
    descriptor = name_end + 1
    header_crc_at = descriptor + 17
    if header_crc_at + 2 > len(payload):
        raise UefError(
            f"truncated CFS header in chunk {chunk_index} at &{chunk_offset:06X}"
        )
    load, execution, block_number, data_length, flags, next_address = \
        struct.unpack_from("<IIHHBI", payload, descriptor)
    data_at = header_crc_at + 2
    data_crc_at = data_at + data_length
    # Zero-byte catalogue markers in published Electron UEFs end after the
    # header CRC. There is no data payload and therefore no data CRC field.
    data_crc_size = 0 if data_length == 0 else 2
    expected_length = data_crc_at + data_crc_size
    if expected_length > len(payload):
        raise UefError(
            f"CFS block in chunk {chunk_index} at &{chunk_offset:06X} "
            f"declares {data_length} data bytes but chunk shape is "
            f"{len(payload)} bytes, requires at least {expected_length}"
        )
    header_bytes = payload[1:header_crc_at]
    data = payload[data_at:data_crc_at]
    stored_header_crc = int.from_bytes(payload[header_crc_at:data_at], "big")
    stored_data_crc = (int.from_bytes(payload[data_crc_at:expected_length], "big")
                       if data_crc_size else None)
    return {
        "chunk_index": chunk_index,
        "chunk_offset": chunk_offset,
        "name": payload[1:name_end].decode("latin-1"),
        "name_hex": payload[1:name_end].hex(),
        "load_address": load,
        "execution_address": execution,
        "block_number": block_number,
        "data_length": data_length,
        "flags": flags,
        "last_block": bool(flags & 0x80),
        "locked": bool(flags & 0x01),
        "next_address": next_address,
        "header_crc": stored_header_crc,
        "header_crc_ok": tape_crc(header_bytes) == stored_header_crc,
        "data_crc": stored_data_crc,
        "data_crc_ok": data_crc_size == 0 or tape_crc(data) == stored_data_crc,
        # Original WiCFS subtracts the parsed header, data and CRC from the
        # enclosing chunk length and skips any residual bytes. Some published
        # images use that allowance for one or more trailing bytes.
        "trailing_length": len(payload) - expected_length,
        "trailing_hex": payload[expected_length:].hex(),
    }


def decode_container(encoded: bytes) -> tuple[bytes, list[str], str | None]:
    """Decode the same raw/gzip/single-entry ZIP forms accepted by Pi1MHz."""
    formats: list[str] = []
    member: str | None = None
    data = encoded
    for _ in range(3):
        if data.startswith(MAGIC):
            formats.append("raw")
            return data, formats, member
        if data.startswith(b"\x1f\x8b"):
            formats.append("gzip")
            try:
                data = gzip.decompress(data)
            except (EOFError, OSError) as exc:
                raise UefError(f"invalid gzip container: {exc}") from exc
            continue
        if data.startswith(b"PK\x03\x04"):
            formats.append("zip")
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    files = [entry for entry in archive.infolist()
                             if not entry.is_dir()]
                    if len(files) != 1:
                        raise UefError(
                            f"ZIP must contain exactly one file, found {len(files)}"
                        )
                    member = files[0].filename
                    data = archive.read(files[0])
            except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
                raise UefError(f"invalid ZIP container: {exc}") from exc
            continue
        break
    raise UefError("input is not a raw UEF, gzip UEF or single-file ZIP UEF")


def inspect_uef(path: Path) -> dict[str, Any]:
    encoded = path.read_bytes()
    raw, formats, member = decode_container(encoded)
    if len(raw) < HEADER_SIZE:
        raise UefError(f"truncated UEF header: {len(raw)} bytes")
    major, minor = raw[10], raw[11]
    chunks: list[dict[str, Any]] = []
    cfs_blocks: list[dict[str, Any]] = []
    position = HEADER_SIZE
    last_0100_end: int | None = None
    last_data_end: int | None = None
    while position < len(raw):
        header = position
        if len(raw) - position < 6:
            raise UefError(
                f"truncated chunk header at &{position:06X}: "
                f"{len(raw) - position} byte(s) remain"
            )
        chunk_type, length = struct.unpack_from("<HI", raw, position)
        data_start = position + 6
        end = data_start + length
        if end > len(raw):
            raise UefError(
                f"chunk &{chunk_type:04X} at &{header:06X} declares "
                f"{length} bytes, {len(raw) - data_start} available"
            )
        data_bearing = chunk_type in DATA_CHUNKS
        if chunk_type == 0x0100:
            last_0100_end = end
        if data_bearing:
            last_data_end = end
        chunks.append({
            "index": len(chunks),
            "offset": header,
            "type": chunk_type,
            "type_hex": f"{chunk_type:04X}",
            "name": CHUNK_NAMES.get(chunk_type, "unknown"),
            "length": length,
            "data_offset": data_start,
            "end": end,
            "data_bearing": data_bearing,
        })
        if chunk_type == 0x0100:
            block = inspect_cfs_block(
                raw[data_start:end], len(chunks) - 1, header
            )
            if block is not None:
                cfs_blocks.append(block)
        position = end

    cfs_issues: list[str] = []
    expected_block: int | None = None
    active_name: str | None = None
    for block in cfs_blocks:
        if expected_block is None:
            if block["block_number"] != 0:
                cfs_issues.append(
                    f"{block['name']!r} starts at block "
                    f"&{block['block_number']:04X}"
                )
            active_name = block["name"]
            expected_block = block["block_number"]
        if block["name"] != active_name or block["block_number"] != expected_block:
            cfs_issues.append(
                f"expected {active_name!r} block &{expected_block:04X}, got "
                f"{block['name']!r} block &{block['block_number']:04X}"
            )
            active_name = block["name"]
            expected_block = block["block_number"]
        if not block["header_crc_ok"]:
            cfs_issues.append(
                f"{block['name']!r} block &{block['block_number']:04X} "
                "has a bad header CRC"
            )
        if not block["data_crc_ok"]:
            cfs_issues.append(
                f"{block['name']!r} block &{block['block_number']:04X} "
                "has a bad data CRC"
            )
        expected_block = block["block_number"] + 1
        if block["last_block"]:
            expected_block = None
            active_name = None
    if expected_block is not None:
        cfs_issues.append(
            f"{active_name!r} ends without a final-block flag after "
            f"block &{expected_block - 1:04X}"
        )

    # Report the earlier 0.1.55 trimming experiment separately from the full
    # compatibility length. The candidate default presents every valid chunk.
    legacy_trim_length = last_0100_end or len(raw)
    return {
        "path": str(path),
        "encoded_length": len(encoded),
        "decoded_length": len(raw),
        "container_chain": formats,
        "zip_member": member,
        "uef_version": {"major": major, "minor": minor},
        "chunks": chunks,
        "cfs_blocks": cfs_blocks,
        "cfs_issues": cfs_issues,
        "last_0100_end": last_0100_end,
        "last_data_end": last_data_end,
        "compatibility_length": len(raw),
        "legacy_trim_length": legacy_trim_length,
        "legacy_trimmed_bytes": len(raw) - legacy_trim_length,
    }


def text_report(report: dict[str, Any]) -> str:
    version = report["uef_version"]
    lines = [
        f"File: {report['path']}",
        f"Container: {' -> '.join(report['container_chain'])}",
        f"Encoded: {report['encoded_length']} bytes",
        f"Decoded: {report['decoded_length']} bytes",
        f"UEF version: {version['major']}.{version['minor']}",
        "",
        " idx  offset  type  length  data    end     class/name",
    ]
    for chunk in report["chunks"]:
        classification = "data" if chunk["data_bearing"] else "control"
        lines.append(
            f"{chunk['index']:4d}  {chunk['offset']:06X}  "
            f"{chunk['type_hex']}  {chunk['length']:6d}  "
            f"{chunk['data_offset']:06X}  {chunk['end']:06X}  "
            f"{classification}: {chunk['name']}"
        )
    lines.extend(["", " CFS file    block  load      exec      len   flags  CRC"])
    for block in report["cfs_blocks"]:
        crc = "OK" if block["header_crc_ok"] and block["data_crc_ok"] else "BAD"
        display_name = block["name"].encode("unicode_escape").decode("ascii")
        lines.append(
            f" {display_name:<11} {block['block_number']:04X}  "
            f"{block['load_address']:08X}  {block['execution_address']:08X}  "
            f"{block['data_length']:04X}  {block['flags']:02X}     {crc}"
        )
    lines.append(
        "CFS validation: " +
        ("OK" if not report["cfs_issues"] else "; ".join(report["cfs_issues"]))
    )
    lines.extend([
        "",
        f"Last &0100 end: {report['last_0100_end']}",
        f"Last data-bearing end: {report['last_data_end']}",
        f"Compatibility length: {report['compatibility_length']} bytes",
        f"Legacy 0.1.55 trim length: {report['legacy_trim_length']} bytes",
        f"Legacy 0.1.55 tail removed: {report['legacy_trimmed_bytes']} bytes",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="map a raw, gzip or single-file ZIP UEF byte-for-byte"
    )
    parser.add_argument("uef", type=Path)
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable JSON")
    args = parser.parse_args()
    try:
        report = inspect_uef(args.uef)
    except (OSError, UefError) as exc:
        print(f"uef_map: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(text_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import shutil
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


RECOMMENDED_ARGS = (
    "-map",
    "0",
    "-c",
    "copy",
    "-movflags",
    "+faststart",
    "-avoid_negative_ts",
    "make_zero",
)


@dataclass(frozen=True)
class Atom:
    type: str
    offset: int
    size: int


@dataclass(frozen=True)
class Mp4Check:
    path: Path
    atoms: tuple[Atom, ...]
    problems: tuple[str, ...]
    truncated: bool

    @property
    def needs_remux(self) -> bool:
        return bool(self.problems)


def read_top_level_atoms(path: Path, limit: int) -> tuple[tuple[Atom, ...], bool]:
    file_size = path.stat().st_size
    atoms: list[Atom] = []
    offset = 0
    truncated = False

    with path.open("rb") as file:
        while offset + 8 <= file_size and len(atoms) < limit:
            file.seek(offset)
            header = file.read(16)
            if len(header) < 8:
                break

            atom_size = struct.unpack(">I", header[:4])[0]
            atom_type = header[4:8].decode("latin1", errors="replace")
            header_size = 8

            if atom_size == 1:
                if len(header) < 16:
                    break
                atom_size = struct.unpack(">Q", header[8:16])[0]
                header_size = 16
            elif atom_size == 0:
                atom_size = file_size - offset

            if atom_size < header_size or offset + atom_size > file_size:
                atoms.append(Atom(atom_type, offset, max(atom_size, 0)))
                break

            atoms.append(Atom(atom_type, offset, atom_size))
            offset += atom_size

        if offset + 8 <= file_size:
            truncated = True

    return tuple(atoms), truncated


def check_mp4(path: Path, max_atoms: int) -> Mp4Check:
    atoms, truncated = read_top_level_atoms(path, max_atoms)
    problems: list[str] = []

    moov_atoms = [atom for atom in atoms if atom.type == "moov"]
    mdat_atoms = [atom for atom in atoms if atom.type == "mdat"]

    if not atoms:
        problems.append("无法读取 MP4 顶层 atom")
    if not moov_atoms:
        problems.append("缺少 moov 元数据 atom")
    if not mdat_atoms:
        problems.append("缺少 mdat 媒体数据 atom")

    if moov_atoms and mdat_atoms:
        first_moov = moov_atoms[0]
        first_mdat = mdat_atoms[0]
        if first_moov.offset > first_mdat.offset:
            problems.append("moov 在 mdat 后面，浏览器读取 metadata 需要跳到文件尾部")

    if len(mdat_atoms) > 1:
        problems.append(f"存在 {len(mdat_atoms)} 个 mdat 分片，浏览器建立索引可能很慢")

    if not truncated and atoms and atoms[-1].offset + atoms[-1].size != path.stat().st_size:
        problems.append("MP4 atom 结构没有完整覆盖文件，容器可能异常")

    return Mp4Check(path=path, atoms=atoms, problems=tuple(problems), truncated=truncated)


def temp_output_path(path: Path) -> Path:
    return path.with_name(f"{path.stem}.remuxing{path.suffix}")


def ffmpeg_command(ffmpeg: str, source: Path, target: Path) -> list[str]:
    command = [ffmpeg, "-hide_banner", "-y"]
    command.extend(["-i", str(source)])
    command.extend(RECOMMENDED_ARGS)
    command.append(str(target))
    return command


def quote_command(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


def scan_mp4_files(root: Path, pattern: str, limit: int | None) -> list[Path]:
    files = sorted(
        (path for path in root.rglob(pattern) if path.is_file()),
        key=lambda item: str(item).casefold(),
    )
    return files[:limit] if limit is not None else files


def run_command(command: list[str]) -> int:
    completed = subprocess.run(command, check=False)
    return completed.returncode


def remux_in_place(ffmpeg: str, source: Path) -> int:
    target = temp_output_path(source)
    if target.exists():
        target.unlink()

    command = ffmpeg_command(ffmpeg, source, target)
    returncode = run_command(command)
    if returncode != 0:
        if target.exists():
            target.unlink()
        return returncode

    if not target.exists() or target.stat().st_size == 0:
        if target.exists():
            target.unlink()
        return 1

    target.replace(source)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "扫描当前目录及子目录中的 MP4。默认 dry-run，只打印需要重封装的文件和 ffmpeg 命令。"
        )
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="要扫描的目录，默认当前目录。",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="实际执行 ffmpeg 重封装。默认不执行。",
    )
    parser.add_argument(
        "--ffmpeg",
        default="ffmpeg",
        help="ffmpeg 可执行文件路径，默认从 PATH 查找。",
    )
    parser.add_argument(
        "--max-atoms",
        type=int,
        default=256,
        help="每个文件最多读取的 MP4 顶层 atom 数量，默认 256。",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="打印正常文件；默认只打印有问题的文件。",
    )
    parser.add_argument(
        "--pattern",
        default="*.mp4",
        help="扫描文件匹配模式，默认 *.mp4。例如 *sone-477*.mp4。",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="最多扫描多少个文件，默认不限制。用于先小范围测试。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    ffmpeg = shutil.which(args.ffmpeg) or args.ffmpeg

    if not root.exists() or not root.is_dir():
        print(f"目录不存在: {root}", file=sys.stderr)
        return 2

    files = scan_mp4_files(root, args.pattern, args.limit)
    print(f"扫描目录: {root}")
    print(f"发现 MP4: {len(files)} 个")
    if not args.apply:
        print("当前为 dry-run，不会执行 ffmpeg，也不会写入文件。")
        print("实际执行时会先写入 .remuxing.mp4 临时文件，成功后覆盖源 MP4。")

    changed = 0
    failed = 0

    for path in files:
        try:
            result = check_mp4(path, max(16, args.max_atoms))
        except OSError as exc:
            failed += 1
            print(f"\n[读取失败] {path}")
            print(f"  {exc}")
            continue

        if not result.needs_remux:
            if args.verbose:
                print(f"[正常] {path}")
            continue

        changed += 1
        target = temp_output_path(path)
        command = ffmpeg_command(ffmpeg, path, target)

        print(f"\n[建议重封装] {path}")
        for problem in result.problems:
            print(f"  - {problem}")
        # print(f"  临时输出: {target}")
        # print("  完成动作: 成功后覆盖源 MP4")
        # print(f"  命令: {quote_command(command)}")

        if args.apply:
            returncode = remux_in_place(ffmpeg, path)
            if returncode != 0:
                failed += 1
                print(f"  ffmpeg 失败，退出码: {returncode}")
            else:
                print("  已覆盖源 MP4")

    print()
    print(f"扫描完成。建议重封装: {changed} 个，失败: {failed} 个。")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

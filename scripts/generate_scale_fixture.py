from __future__ import annotations

import argparse
import io
import json
import zipfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = REPOSITORY_ROOT / "project_templates" / "research_football" / "clean"


def _jsonl(rows: list[dict]) -> bytes:
    return ("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n").encode("utf-8")


def build_scale_package(sample_count: int = 250, comments_per_sample: int = 20, frames_per_sample: int = 3) -> bytes:
    manifest = json.loads((TEMPLATE_ROOT / "codeflow_project.json").read_text(encoding="utf-8"))
    manifest.update({
        "project_id": f"codeflow_scale_{sample_count}",
        "name": f"CodeFlow {sample_count} 条规模验收",
        "dataset_version": "scale-v1",
    })
    manifest["workflow"]["default_coders"] = ["scale_coder_01", "scale_coder_02", "scale_coder_03"]
    samples, comments, frames, assets = [], [], [], []
    for sample_index in range(1, sample_count + 1):
        sample_id = f"S{sample_index:05d}"
        samples.append({
            "sample_id": sample_id, "title": f"规模验收样本 {sample_index}",
            "duration_seconds": 90.0, "split": "scale", "technical_qc": "pass",
            "account": "scale-fixture", "like_count": sample_index,
        })
        assets.append({
            "asset_id": f"A{sample_index:05d}", "sample_id": sample_id,
            "asset_type": "video", "video_path": "videos/v001.mp4", "duration_seconds": 90.0,
        })
        for comment_index in range(1, comments_per_sample + 1):
            comments.append({
                "comment_id": f"C{sample_index:05d}-{comment_index:03d}", "sample_id": sample_id,
                "text": f"样本 {sample_index} 的清洗评论 {comment_index}",
                "like_count": comments_per_sample - comment_index, "rank_by_like": comment_index,
                "comment_type": "text",
            })
        for frame_index in range(1, frames_per_sample + 1):
            frames.append({
                "frame_id": f"F{sample_index:05d}-{frame_index:02d}", "sample_id": sample_id,
                "time_seconds": float(frame_index * 10), "frame_set": "scale",
                "path": "frames/v001_1.png",
            })
    replacements = {
        "codeflow_project.json": json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        "samples.jsonl": _jsonl(samples), "comments.jsonl": _jsonl(comments),
        "frames.jsonl": _jsonl(frames), "assets.jsonl": _jsonl(assets),
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in TEMPLATE_ROOT.rglob("*"):
            if path.is_file():
                relative = path.relative_to(TEMPLATE_ROOT).as_posix()
                archive.writestr(f"clean/{relative}", replacements.get(relative, path.read_bytes()))
    return output.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 CodeFlow 多表规模验收包")
    parser.add_argument("--samples", type=int, default=250)
    parser.add_argument("--comments-per-sample", type=int, default=20)
    parser.add_argument("--frames-per-sample", type=int, default=3)
    parser.add_argument("--output", type=Path, default=REPOSITORY_ROOT / "artifacts" / "scale-250.zip")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    content = build_scale_package(args.samples, args.comments_per_sample, args.frames_per_sample)
    args.output.write_bytes(content)
    print(json.dumps({"output": str(args.output), "bytes": len(content), "samples": args.samples}, ensure_ascii=False))


if __name__ == "__main__":
    main()

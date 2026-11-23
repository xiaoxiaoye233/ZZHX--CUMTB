# -*- coding: utf-8 -*-
"""版本层：一次生成 = 一个数据版本。只管记账与对比，不碰数据本身。

目录约定（都在 `data/`，整目录不入库）：
    data/builds/<数据版本>/记录.json     这一次的数字、文件数、断言数
    data/builds/<数据版本>/文件清单.csv  每个文件的字节数与 sha256
    data/builds/<数据版本>/变更说明.md   与上一版比，数字和文件各变了什么

**保留策略**：目前一份都不删（老师用过的那一版要能追）。
等版本策略定下来再调 `prune()` 里的 keep 参数，别在别处写死删除逻辑。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def builds_dir(root: str | Path | None = None) -> Path:
    return Path(root or ROOT) / "data" / "builds"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def list_builds(root: str | Path | None = None) -> list[dict]:
    """按版本号排序（版本号是 20260101-0900 这种，字典序就是时间序）。"""
    base = builds_dir(root)
    if not base.exists():
        return []
    builds = []
    for path in sorted(p for p in base.iterdir() if p.is_dir()):
        record = path / "记录.json"
        if not record.exists():
            continue
        data = _read_json(record)
        data.setdefault("build_id", path.name)
        builds.append(data)
    return builds


def latest_build(root: str | Path | None = None, exclude: str | None = None) -> dict | None:
    for build in reversed(list_builds(root)):
        if exclude and build["build_id"] == exclude:
            continue
        return build
    return None


def read_manifest(root: str | Path | None, build_id: str) -> dict[str, str]:
    """{文件路径: sha256}；这份台账没有文件清单时抛错，别静默当成空表。"""
    path = builds_dir(root) / build_id / "文件清单.csv"
    if not path.exists():
        raise FileNotFoundError(f"台账 {build_id} 里没有 文件清单.csv：{path}")
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {row["文件"]: row["sha256"] for row in csv.DictReader(f)}


def diff(before: dict | None, after: dict, root: str | Path | None = None) -> dict:
    """两个版本比一比：数字变了哪些、文件变了哪些。"""
    before = before or {}
    numbers = []
    prev_numbers = before.get("汇总") or {}
    cur_numbers = after.get("汇总") or {}
    for name in list(prev_numbers) + [k for k in cur_numbers if k not in prev_numbers]:
        old, new = prev_numbers.get(name), cur_numbers.get(name)
        if old != new:
            delta = ""
            if isinstance(old, (int, float)) and isinstance(new, (int, float)):
                change = round(new - old, 4)
                delta = f"{change:+}" if change else ""
            numbers.append({"name": name, "before": old, "after": new, "delta": delta})

    files = {"added": [], "changed": [], "removed": []}
    missing_manifest = ""
    if before.get("build_id") and after.get("build_id"):
        try:
            old_manifest = read_manifest(root, before["build_id"])
            new_manifest = read_manifest(root, after["build_id"])
        except FileNotFoundError as exc:
            # 上一版台账不完整时，绝不能把 118 个文件全报成"新增"
            missing_manifest = str(exc)
            old_manifest = new_manifest = {}
        if old_manifest and new_manifest:
            files["added"] = sorted(set(new_manifest) - set(old_manifest))
            files["removed"] = sorted(set(old_manifest) - set(new_manifest))
            files["changed"] = sorted(p for p in set(old_manifest) & set(new_manifest)
                                      if old_manifest[p] != new_manifest[p])

    return {
        "from": before.get("build_id") or "（没有上一版）",
        "to": after.get("build_id", ""),
        "numbers": numbers,
        "files": files,
        "file_count": {"before": before.get("file_count"), "after": after.get("file_count")},
        "assertions": {
            "before": before.get("assertions_passed"),
            "after": after.get("assertions_passed"),
            "mode_before": before.get("assertion_mode", ""),
            "mode_after": after.get("assertion_mode", ""),
        },
        "data_source": {"before": before.get("data_source", ""), "after": after.get("data_source", "")},
        "missing_manifest": missing_manifest,
    }


def change_note_text(result: dict) -> str:
    lines = [f"# 这次改了什么（{result['from']} → {result['to']}）", ""]
    files = result["files"]
    lines.append(f"- 文件：{result['file_count']['before']} → {result['file_count']['after']}；"
                 f"新增 {len(files['added'])}、改动 {len(files['changed'])}、删除 {len(files['removed'])}")
    ast = result["assertions"]
    if ast.get("mode_before") == ast.get("mode_after") or not ast.get("mode_before"):
        lines.append(f"- 断言：{ast['before']} → {ast['after']}")
    else:
        # 参考数据跑 81 条（含 30 条基准），换一批数据只跑 27 条通用检查，
        # 直接写 "81 → 27" 会让人以为检查变少了
        lines.append(f"- 断言：{ast['before']} 条（{ast['mode_before']}）→ {ast['after']} 条（{ast['mode_after']}）"
                     "——两次数据源不同，能跑的检查条数本来就不一样，不是质量下降")
    source = result.get("data_source") or {}
    if source.get("before") and source.get("after") and source["before"] != source["after"]:
        lines.append(f"- ⚠ 数据源变了：`{source['before']}` → `{source['after']}`；"
                     "下面这些数字是两批数据的，不能当成\"同一个库前后变化\"来读")
    if result.get("missing_manifest"):
        lines.append(f"- ⚠ 文件对比没做成：{result['missing_manifest']}"
                     "（上一版台账缺文件清单，所以下面不列文件增删改）")
    lines.append("")
    if result["numbers"]:
        lines.append(f"## 数字变化（{len(result['numbers'])} 处）")
        lines.append("")
        lines.append("| 指标 | 上一次 | 这一次 | 变化 |")
        lines.append("|---|---|---|---|")
        for row in result["numbers"]:
            lines.append(f"| {row['name']} | {row['before']} | {row['after']} | {row['delta']} |")
        lines.append("")
    else:
        lines += ["## 数字变化", "", "关键数字一个都没变（改的是代码或文件结构）。", ""]
    for key, label in (("added", "新增文件"), ("changed", "改动文件"), ("removed", "删除文件")):
        if files[key]:
            lines.append(f"### {label}（{len(files[key])}）")
            lines.append("")
            lines += [f"- `{p}`" for p in files[key][:20]]
            if len(files[key]) > 20:
                lines.append(f"- …另有 {len(files[key]) - 20} 个，见 文件清单.csv")
            lines.append("")
    return "\n".join(lines)


def write_change_note(result: dict, root: str | Path | None = None) -> Path:
    path = builds_dir(root) / result["to"] / "变更说明.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(change_note_text(result), encoding="utf-8")
    return path


def prune(root: str | Path | None = None, keep: int | None = None) -> list[str]:
    """删旧版本。默认 keep=None = 一份都不删。

    老师用过的那一版要能追；正式期再定保留几份，别在这个函数之外删目录。
    keep 是"留几份"，必须 ≥1；只删有 `记录.json` 的目录，别碰别的临时文件夹。
    """
    if keep is None:
        return []
    if keep < 1:
        raise ValueError(f"keep 至少要留 1 份，收到 {keep}（想一份不删就别调这个函数）")
    import shutil

    base = builds_dir(root)
    builds = sorted(p for p in base.iterdir() if p.is_dir() and (p / "记录.json").exists()) if base.exists() else []
    removed = []
    for stale in builds[:-keep]:
        shutil.rmtree(stale)
        removed.append(stale.name)
    return removed

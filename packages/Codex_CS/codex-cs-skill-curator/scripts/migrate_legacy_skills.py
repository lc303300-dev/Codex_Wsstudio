from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from inspect_skill_source import decode_source, inspect
from prepare_dt_supplement import build_request
from skill_package import file_sha256, validate_package


SCRIPT_ROOT = Path(__file__).resolve().parent
TEMPLATE_ROOT = SCRIPT_ROOT.parent / "assets" / "business-skill-template"
DEFAULT_SKILLS_ROOT = Path(r"F:\LiuCan\AI\Codex\Codex_CS\skills")
DEFAULT_OUTPUT_ROOT = Path("staging-migration")


@dataclass(frozen=True)
class MigrationSpec:
    skill_id: str
    display_name: str
    description: str
    sources: tuple[str, ...]
    skip_reason: str | None
    references: list[dict]
    allowed_modes: list[str]
    timing_strategy: str = "adaptive"
    transition_strategy: str = "adaptive"


SPECS = [
    MigrationSpec(
        skill_id="giant-3d-logo-landmark-video",
        display_name="巨型3D Logo 地标巡游视频",
        description="将3D Logo设定图与一张或多张城市地标参考素材编排为多场景硬切、身份稳定且引用绑定明确的视频提示词。",
        sources=(
            "巨型3D立体Logo地标巡游多场景硬切视频提示词生成 Skill.md",
            "giant-3d-logo-landmark-video/SKILL.md",
        ),
        skip_reason=None,
        references=[
            {
                "id": "logo-design",
                "media_type": "image",
                "role": "identity",
                "description": "3D Logo设定图，用于锁定徽标、文字、排列、比例、厚度、材质和透视",
                "required": True,
                "min_count": 1,
                "max_count": 1,
                "ordered": True,
                "observation_required": True,
            },
            {
                "id": "landmark-scenes",
                "media_type": "image",
                "role": "scene",
                "description": "按输入顺序绑定的城市地标或场景参考，可由用户指定为场景参考、严格起始帧或严格结束帧",
                "required": True,
                "min_count": 1,
                "max_count": None,
                "ordered": True,
                "observation_required": True,
            },
        ],
        allowed_modes=["image2video", "frames2video", "multimodal2video"],
    ),
    MigrationSpec(
        skill_id="giant-ip-landmark-parade",
        display_name="巨型IP地标巡游硬切视频",
        description="将IP角色设定图与多张城市地标实景合成参考编排为巨型卡通IP巡游、道具互动和多场景硬切视频提示词。",
        sources=("巨型IP地标巡游多场景硬切视频提示词生成 Skill.md",),
        skip_reason=None,
        references=[
            {
                "id": "ip-character",
                "media_type": "image",
                "role": "identity",
                "description": "IP角色详细说明图或四视图，用于固定角色外观、比例、表情、材质和道具身份",
                "required": True,
                "min_count": 1,
                "max_count": 1,
                "ordered": True,
                "observation_required": True,
            },
            {
                "id": "parade-scenes",
                "media_type": "image",
                "role": "scene",
                "description": "按顺序提供的城市地标或实景合成参考，用于多场景巡游与硬切镜头绑定",
                "required": True,
                "min_count": 1,
                "max_count": None,
                "ordered": True,
                "observation_required": True,
            },
        ],
        allowed_modes=["image2video", "frames2video", "multimodal2video"],
    ),
    MigrationSpec(
        skill_id="architectural-assembly-reveal",
        display_name="建筑特写至全貌动态组装视频",
        description="将建筑外观、构造节点、室内、露台、庭院等多张参考图编排为从特写到全貌的动态拆解组装展示提示词。",
        sources=("建筑特写至全貌拆解组装动画视频提示词生成 Skill.md",),
        skip_reason=None,
        references=[
            {
                "id": "assembly-frames",
                "media_type": "image",
                "role": "end_frame",
                "description": "按镜头顺序提供的建筑参考图，每张图作为对应镜头最后一刻必须抵达的绝对尾帧",
                "required": True,
                "min_count": 1,
                "max_count": None,
                "ordered": True,
                "observation_required": True,
            }
        ],
        allowed_modes=["frames2video", "multimodal2video"],
        transition_strategy="skill_defined",
    ),
    MigrationSpec(
        skill_id="sci-fi-city-promo",
        display_name="科幻风格城市宣传片",
        description="将城市名称、时长、比例和城市地标参考素材转化为未来城市、地方文化与数字光流结合的宣传片视频提示词。",
        sources=("科幻风格城市宣传片提示词生成Skill.md",),
        skip_reason=None,
        references=[
            {
                "id": "city-visual-references",
                "media_type": "image",
                "role": "scene",
                "description": "城市天际线、现代地标、文化建筑、江河湖海、道路夜景或代表性视觉符号参考",
                "required": True,
                "min_count": 1,
                "max_count": None,
                "ordered": True,
                "observation_required": True,
            }
        ],
        allowed_modes=["image2video", "multimodal2video"],
    ),
    MigrationSpec(
        skill_id="city-real-estate-habitat-promo",
        display_name="城市与地产人居宣传片",
        description="将城市地标、楼盘布局、立面细节和阳台景观等参考素材编排为城市叙事到社区平视穿梭的人居宣传片提示词。",
        sources=("城市与地产人居宣传片提示词生成Skill.md",),
        skip_reason=None,
        references=[
            {
                "id": "city-context",
                "media_type": "image",
                "role": "scene",
                "description": "城市级地标、江河、桥梁、天际线或宏观城市叙事参考",
                "required": True,
                "min_count": 1,
                "max_count": None,
                "ordered": True,
                "observation_required": True,
            },
            {
                "id": "real-estate-context",
                "media_type": "image",
                "role": "scene",
                "description": "楼盘鸟瞰布局、立面细节、社区空间或阳台景观参考，用于楼盘几何和人居空间绑定",
                "required": True,
                "min_count": 1,
                "max_count": None,
                "ordered": True,
                "observation_required": True,
            },
        ],
        allowed_modes=["image2video", "multimodal2video"],
    ),
    MigrationSpec(
        skill_id="dawn-mist-aerial-real-estate",
        display_name="晨曦云雾航拍地产地标视频",
        description="将核心建筑、多张实景或效果合成图、时长和比例转化为晨曦云雾、沉稳航拍和硬切镜头的地产地标提示词。",
        sources=("晨曦云雾航拍风_地产商业地标视频提示词生成Skill.md",),
        skip_reason=None,
        references=[
            {
                "id": "aerial-scene-frames",
                "media_type": "image",
                "role": "scene",
                "description": "按时长和镜头规划提供的建筑、环境、水面、意象、立面或宏观定场参考图",
                "required": True,
                "min_count": 1,
                "max_count": None,
                "ordered": True,
                "observation_required": True,
            }
        ],
        allowed_modes=["image2video", "frames2video", "multimodal2video"],
        transition_strategy="skill_defined",
    ),
    MigrationSpec(
        skill_id="legacy-video-skill-template",
        display_name="旧版视频 Skill 模板",
        description="旧 Codex_CS 模板文件，仅作为迁移参考，不作为正式业务 Skill 发布。",
        sources=("Skill_MB.md",),
        skip_reason="template_only",
        references=[],
        allowed_modes=[],
    ),
]


def strip_wrappers(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if re.search(r"(?i)START OF FILE|END OF FILE", line):
            continue
        lines.append(line.rstrip())
    text = "\n".join(lines).strip()
    text = text.replace("\\---", "---")
    text = re.sub(r"`generate_video`", "统一视频生成入口", text)
    text = re.sub(r"\bgenerate_video\b", "统一视频生成入口", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def render_template(destination: Path, spec: MigrationSpec) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(TEMPLATE_ROOT, destination)
    replacements = {
        "skill_id": spec.skill_id,
        "display_name": spec.display_name,
        "description": spec.description,
        "short_description": (spec.description[:63] if len(spec.description) > 64 else spec.description),
    }
    for path in destination.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8-sig")
        for key, value in replacements.items():
            text = text.replace("{{" + key + "}}", value)
        path.write_text(text, encoding="utf-8")


def core_task(spec: MigrationSpec) -> str:
    return (
        f"根据已确认的参考素材、用户当前指令和本 Skill 的专业经验，编写“{spec.display_name}”视频生成提示词。"
        "提示词必须保持素材顺序、主体身份、镜头意图、时间推进和结尾条件一致，并在完成后交由主工作流确认。"
    )


def build_contract(destination: Path, spec: MigrationSpec) -> None:
    contract_path = destination / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["references"] = spec.references
    contract["video"]["allowed_modes"] = spec.allowed_modes
    contract["authoring"]["timing_strategy"] = spec.timing_strategy
    contract["authoring"]["transition_strategy"] = spec.transition_strategy
    write_text(contract_path, json.dumps(contract, ensure_ascii=False, indent=2) + "\n")


def build_skill_md(destination: Path, spec: MigrationSpec) -> None:
    body = f"""---
name: {spec.skill_id}
description: {spec.description}
---

# {spec.display_name}

## 核心任务

{core_task(spec)}

## 知识加载

- 创作前读取 `contract.json`，严格按素材槽顺序绑定参考素材。
- 编写提示词时读取 `references/creative-guidance.md`。
- 需要采用社区实践时读取 `references/community-experience.md`，只使用符合当前条件的经验。
- 定稿前读取 `references/failure-cases.md`。
- 仅在需要相似案例或用户要求时读取 `references/examples.md`；不得用示例改变素材契约。

## 执行原则

1. 用户当前明确指令具有最高优先级。
2. 只依据已确认素材、用户说明和本 Skill 知识编写提示词。
3. 保持素材引用顺序、主体身份、因果关系、时间顺序和结尾条件。
4. 使用中文为主，保留必要的专业英文并给出中文含义。
5. 完成后交由 Codex_CS 主工作流展示并取得用户确认。

## 禁止事项

- 不选择实际生成 provider、模型、分辨率、轮询或下载策略。
- 不直接提交图片或视频生成任务。
- 不把示例中的项目、地点、角色或镜头数量变成通用规则。
- 不在素材信息存在歧义时自行猜测。
"""
    write_text(destination / "SKILL.md", body)


def extract_failure_section(text: str) -> str:
    match = re.search(r"(?is)(?:常见失败案例与修正方法|失败案例.*)", text)
    return match.group(0).strip() if match else "原始资料未提供独立失败案例。"


def extract_examples(text: str) -> str:
    matches = list(re.finditer(r"(?im)^(?:#+\s*)?(?:示例|合格镜头写法示例|示例输入|示例输出).*", text))
    if not matches:
        return "原始资料未提供示例。"
    start = matches[0].start()
    failure = re.search(r"(?im)^.*常见失败案例与修正方法.*$", text[start:])
    end = start + failure.start() if failure else len(text)
    return text[start:end].strip()


def build_references(destination: Path, spec: MigrationSpec, source_blocks: list[dict]) -> None:
    merged = "\n\n".join(
        f"## 来源：{block['name']}\n\n{block['text']}" for block in source_blocks
    ).strip()
    first_text = source_blocks[0]["text"]
    provenance = (
        "> 来源：旧 Codex_CS 迁移；状态：needs_review；用途：保留经验，不定义素材契约。"
        "历史平台、模型或 CLI 表述只作为来源背景，不决定当前执行。\n\n"
    )
    write_text(
        destination / "references" / "creative-guidance.md",
        "# 专业创作经验\n\n" + provenance + merged + "\n",
    )
    write_text(
        destination / "references" / "community-experience.md",
        "# 社区经验与来源背景\n\n"
        + provenance
        + "原始资料中的实测经验、常见问题、修正方法和历史提示词经验已在下方按来源保留；使用时必须按当前任务条件判断适用性。\n\n"
        + merged
        + "\n",
    )
    write_text(
        destination / "references" / "failure-cases.md",
        "# 失败案例与规避\n\n" + provenance + extract_failure_section(first_text) + "\n",
    )
    write_text(
        destination / "references" / "examples.md",
        "# 示例\n\n"
        + provenance
        + "示例仅帮助理解提示词组织方式，不定义素材契约，不覆盖用户当前指令。\n\n"
        + extract_examples(first_text)
        + "\n",
    )


def source_record(path: Path) -> dict:
    text, encoding = decode_source(path)
    return {
        "name": path.name,
        "path": str(path),
        "encoding": encoding,
        "sha256": file_sha256(path),
        "text": strip_wrappers(text),
        "inspection": inspect(path),
    }


def public_source(item: dict, source_root: Path) -> dict:
    source_path = Path(item["path"])
    try:
        label = source_path.relative_to(source_root).as_posix()
    except ValueError:
        label = item["name"]
    return {
        "name": item["name"],
        "source_label": label,
        "encoding": item["encoding"],
        "sha256": item["sha256"],
    }


def validate_and_report(package: Path) -> tuple[list[dict], dict]:
    issues = [issue.to_dict() for issue in validate_package(package)]
    dt_request = build_request(package)
    write_text(package / "dt-request.json", json.dumps(dt_request, ensure_ascii=False, indent=2) + "\n")
    return issues, dt_request


def migrate(spec: MigrationSpec, source_root: Path, output_root: Path) -> dict:
    source_paths = [source_root / source for source in spec.sources]
    sources = [source_record(path) for path in source_paths if path.is_file()]
    missing = [str(path) for path in source_paths if not path.is_file()]
    if spec.skip_reason:
        return {
            "skill_id": spec.skill_id,
            "display_name": spec.display_name,
            "status": "skipped",
            "skip_reason": spec.skip_reason,
            "sources": [public_source(item, source_root) for item in sources],
            "missing_sources": missing,
        }
    if missing:
        return {
            "skill_id": spec.skill_id,
            "display_name": spec.display_name,
            "status": "failed",
            "missing_sources": missing,
        }
    destination = output_root / spec.skill_id
    render_template(destination, spec)
    build_contract(destination, spec)
    build_skill_md(destination, spec)
    build_references(destination, spec, sources)
    issues, dt_request = validate_and_report(destination)
    report_path = destination / "intake-report.json"
    report = {
        "schema_version": 1,
        "status": "needs_review" if issues else "ready_for_approval",
        "skill_id": spec.skill_id,
        "display_name": spec.display_name,
        "sources": [public_source(item, source_root) for item in sources],
        "duplicate_check": {
            "classification": "merged_duplicate" if len(sources) > 1 else "new",
            "matches": [public_source(item, source_root)["source_label"] for item in sources[1:]],
        },
        "extraction_summary": {
            "contract_items": len(spec.references),
            "creative_guidance_items": 1,
            "community_experience_items": sum(item["inspection"]["content_summary"]["community_experience_hints"] for item in sources),
            "failure_cases": sum(item["inspection"]["content_summary"]["failure_case_hints"] for item in sources),
            "positive_examples": 1 if dt_request["status"] == "not_required" else 0,
            "negative_examples": 1 if dt_request["status"] == "not_required" else 0,
            "boundary_examples": 1 if dt_request["status"] == "not_required" else 0,
        },
        "reference_summary": spec.references,
        "isolated_legacy_content": [
            finding
            for item in sources
            for finding in item["inspection"]["findings"]
            if finding["code"] in {"EXPORT_WRAPPER", "EXECUTION_COUPLING", "TEXT2VIDEO_MENTION", "NONSTANDARD_METADATA"}
        ],
        "creative_supplement": {
            "status": dt_request["status"],
            "generated_by": "prepare_dt_supplement.py",
            "request_path": "dt-request.json",
            "draft_path": None,
            "requires_user_review": True,
            "reason": ",".join(dt_request["detected_reasons"]) or "source_examples_sufficient",
        },
        "contract_conflicts": [],
        "blocking_questions": [],
        "validation_issues": issues,
        "experience_preservation": {
            "source_claims_accounted_for": True,
            "notes": "Cleaned legacy source experience is preserved in references for review; examples do not define the contract.",
        },
        "user_approval": {"required": True, "approved": False},
    }
    write_text(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return {
        "skill_id": spec.skill_id,
        "display_name": spec.display_name,
        "status": "migrated" if not issues else "needs_fix",
        "package": str(destination),
        "validation_issues": issues,
        "creative_supplement_status": dt_request["status"],
        "sources": report["sources"],
    }


def run_tests(root: Path) -> dict:
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_skill_curator"],
        cwd=root,
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    return {
        "command": "python -m unittest tests.test_skill_curator",
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy Codex_CS video Skills into governed staging packages.")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SKILLS_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--clean", action="store_true", help="Remove the output root before migration.")
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()

    repo_root = SCRIPT_ROOT.parents[1]
    source_root = args.source_root.resolve()
    output_root = (repo_root / args.output_root).resolve() if not args.output_root.is_absolute() else args.output_root.resolve()
    if args.clean and output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    results = [migrate(spec, source_root, output_root) for spec in SPECS]
    summary = {
        "schema_version": 1,
        "source_root": str(source_root),
        "output_root": str(output_root),
        "results": results,
        "counts": {
            "migrated": sum(1 for item in results if item["status"] == "migrated"),
            "needs_fix": sum(1 for item in results if item["status"] == "needs_fix"),
            "skipped": sum(1 for item in results if item["status"] == "skipped"),
            "failed": sum(1 for item in results if item["status"] == "failed"),
        },
    }
    if args.run_tests:
        summary["test_result"] = run_tests(repo_root)
    write_text(output_root / "migration-report.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["counts"]["failed"] == 0 and summary["counts"]["needs_fix"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

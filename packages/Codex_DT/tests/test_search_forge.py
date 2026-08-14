from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "search_forge.py"
SPEC = importlib.util.spec_from_file_location("search_forge", SCRIPT)
assert SPEC and SPEC.loader
search_forge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(search_forge)

UPDATE_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "update_forge_matches.py"
UPDATE_SPEC = importlib.util.spec_from_file_location("update_forge_matches", UPDATE_SCRIPT)
assert UPDATE_SPEC and UPDATE_SPEC.loader
update_forge_matches = importlib.util.module_from_spec(UPDATE_SPEC)
UPDATE_SPEC.loader.exec_module(update_forge_matches)


class SearchForgeTests(unittest.TestCase):
    def test_manifest_queries_take_priority_and_accept_strings(self) -> None:
        manifest = {
            "forge": {"queries_en": ["tracking shot"], "queries_zh": "雨夜"},
            "visual": {"description_zh": "ignored"},
        }
        self.assertEqual(search_forge.query_from_manifest(manifest), "tracking shot 雨夜")

    def test_payload_preserves_source_model_only_as_metadata(self) -> None:
        row = {
            "id": "example-1",
            "title": "雨夜跟拍",
            "description": "社区案例",
            "content": "镜头跟随人物穿过雨夜街道。",
            "author": {"name": "作者", "link": "https://example.test/author"},
            "seedance_version": "2.0",
            "source_project": "community",
            "source_repo": "https://example.test/repo",
            "source_license": "upstream inherited",
        }
        payload = search_forge.row_payload(row, include_content=True, preview_chars=100)
        self.assertEqual(payload["score"], 0)
        self.assertEqual(payload["source_model"], "2.0")
        self.assertEqual(payload["source_metadata"]["model"], "2.0")
        self.assertEqual(payload["content"], row["content"])

    def test_native_ranking_is_joined_to_full_combined_index_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            native = root / "scripts" / "search.py"
            native.parent.mkdir(parents=True)
            native.write_text(
                "import json\nprint(json.dumps([{'id': 'v25'}, {'id': 'v20'}]))\n",
                encoding="utf-8",
            )
            index = root / "combined.index.jsonl"
            records = [
                {"id": "v20", "content": "旧来源但通用的镜头经验", "seedance_version": "2.0"},
                {"id": "v25", "content": "新来源的镜头经验", "seedance_version": "2.5"},
            ]
            index.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records),
                encoding="utf-8",
            )

            results = search_forge.search("镜头", 5, native, index)

        self.assertEqual([row["id"] for row in results], ["v25", "v20"])
        self.assertEqual({row["seedance_version"] for row in results}, {"2.0", "2.5"})

    def test_native_score_keeps_legacy_score_semantics(self) -> None:
        row = {"title": "Rain", "category": "rain", "description": "rain", "content": "rain rain"}
        self.assertEqual(search_forge.native_score(row, "rain"), 11)

    def test_updater_marks_versions_as_provenance_not_constraints(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "shot.json"
            manifest_path.write_text(
                json.dumps({"id": "shot", "forge": {"queries_zh": ["雨夜"]}}, ensure_ascii=False),
                encoding="utf-8",
            )
            payload = {
                "query": "雨夜",
                "matches": [{"id": "community-1", "source_model": "2.0", "content_preview": "rain tracking"}],
            }
            argv = ["update_forge_matches.py", "--manifests", str(manifest_path)]
            with mock.patch.object(update_forge_matches, "search_manifest", return_value=payload), mock.patch(
                "sys.argv", argv
            ):
                self.assertEqual(update_forge_matches.main(), 0)

            updated = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(updated["forge"]["corpus_role"], "general_video_generation_reference")
        self.assertTrue(updated["forge"]["model_versions_are_source_metadata"])
        self.assertEqual(updated["forge"]["matches"][0]["source_model"], "2.0")


if __name__ == "__main__":
    unittest.main()

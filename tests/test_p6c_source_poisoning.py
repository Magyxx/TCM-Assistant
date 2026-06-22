import json
import tempfile
import unittest
from pathlib import Path

from app.knowledge.pipeline import DEFAULT_MANIFEST_PATH, run_p6_pipeline, write_json
from app.knowledge.source_registry import load_source_registry
from app.rag.p6_index_loader import P6IndexLoadError, load_p6_runtime_index


class P6CSourcePoisoningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pipeline = run_p6_pipeline(write_outputs=False)

    def _write_runtime_artifacts(self, root: Path, chunks: list[dict]) -> tuple[Path, Path]:
        index_path = root / "p6_bm25_index.json"
        chunks_path = root / "p6_chunks.jsonl"
        write_json(index_path, self.pipeline["_index"])
        chunks_path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in chunks) + "\n",
            encoding="utf-8",
        )
        return index_path, chunks_path

    def test_contains_pii_runtime_source_fails_closed(self) -> None:
        registry = load_source_registry(DEFAULT_MANIFEST_PATH)
        mutated = json.loads(json.dumps(registry, ensure_ascii=False))
        target = next(source for source in mutated["sources"] if source["source_id"] == "synthetic_p6_policy_001")
        target["contains_pii"] = True

        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "source_registry.json"
            write_json(registry_path, mutated)
            result = run_p6_pipeline(manifest_path=registry_path, write_outputs=False)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["source_review"]["blocked_source_count"], 1)

    def test_chunk_hash_mismatch_fails_closed(self) -> None:
        chunks = [dict(chunk) for chunk in self.pipeline["_chunks"]]
        chunks[0]["content"] += "\npoisoned"

        with tempfile.TemporaryDirectory() as temp_dir:
            index_path, chunks_path = self._write_runtime_artifacts(Path(temp_dir), chunks)
            with self.assertRaisesRegex(P6IndexLoadError, "chunk content hash mismatch"):
                load_p6_runtime_index(
                    index_path=index_path,
                    chunks_path=chunks_path,
                    source_manifest_path=DEFAULT_MANIFEST_PATH,
                )

    def test_source_hash_mismatch_fails_closed(self) -> None:
        chunks = [dict(chunk) for chunk in self.pipeline["_chunks"]]
        chunks[0]["source_hash"] = "sha256:" + "f" * 64

        with tempfile.TemporaryDirectory() as temp_dir:
            index_path, chunks_path = self._write_runtime_artifacts(Path(temp_dir), chunks)
            with self.assertRaisesRegex(P6IndexLoadError, "source hash mismatch"):
                load_p6_runtime_index(
                    index_path=index_path,
                    chunks_path=chunks_path,
                    source_manifest_path=DEFAULT_MANIFEST_PATH,
                )

    def test_stale_index_warning_hook_is_present(self) -> None:
        self.assertIn("source_review_fingerprint", self.pipeline["_index"])
        self.assertIn("stale_index_warnings", self.pipeline["source_registry"])


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from app.knowledge.pipeline import DEFAULT_MANIFEST_PATH, run_p6_pipeline
from app.rag.p6_index_loader import P6IndexLoadError, load_p6_runtime_index
from app.rag.p6_runtime_retriever import P6RuntimeRetriever


class P6BRuntimeRagLoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pipeline = run_p6_pipeline(write_outputs=False)
        cls.base_index = cls.pipeline["_index"]
        cls.base_chunks = cls.pipeline["_chunks"]

    def _write_runtime_artifacts(
        self,
        root: Path,
        *,
        index: dict | None = None,
        chunks: list[dict] | None = None,
        manifest_path: Path | None = None,
    ) -> tuple[Path, Path, Path]:
        index_path = root / "p6_bm25_index.json"
        chunks_path = root / "p6_chunks.jsonl"
        index_path.write_text(
            json.dumps(index or self.base_index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        chunk_rows = chunks if chunks is not None else self.base_chunks
        chunks_path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in chunk_rows) + "\n",
            encoding="utf-8",
        )
        return index_path, chunks_path, manifest_path or DEFAULT_MANIFEST_PATH

    def test_loads_reviewed_p6_artifacts_and_retrieves_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path, chunks_path, manifest_path = self._write_runtime_artifacts(Path(temp_dir))

            loaded = load_p6_runtime_index(
                index_path=index_path,
                chunks_path=chunks_path,
                source_manifest_path=manifest_path,
            )
            pack, trace = P6RuntimeRetriever(loaded_index=loaded).retrieve(
                "chest pain dyspnea offline care",
                top_k=2,
                session_id="unit",
                turn_id="1",
                trace_id="unit-trace",
            )

        self.assertEqual(loaded.chunk_count, 2)
        self.assertEqual(loaded.loaded_source_ids, ["synthetic_p6_policy_001"])
        self.assertGreater(len(pack.evidence), 0)
        self.assertEqual(trace["trace_id"], "unit-trace")
        self.assertFalse(trace["fallback_used"])

    def test_missing_index_file_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_index = Path(temp_dir) / "missing.json"
            chunks_path = Path(temp_dir) / "p6_chunks.jsonl"
            chunks_path.write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(P6IndexLoadError, "missing required P6 artifact"):
                load_p6_runtime_index(
                    index_path=missing_index,
                    chunks_path=chunks_path,
                    source_manifest_path=DEFAULT_MANIFEST_PATH,
                )

    def test_empty_chunk_file_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path, chunks_path, manifest_path = self._write_runtime_artifacts(Path(temp_dir))
            chunks_path.write_text("", encoding="utf-8")

            with self.assertRaisesRegex(P6IndexLoadError, "chunk artifact is empty"):
                load_p6_runtime_index(
                    index_path=index_path,
                    chunks_path=chunks_path,
                    source_manifest_path=manifest_path,
                )

    def test_index_schema_mismatch_fails_closed(self) -> None:
        bad_index = {**self.base_index, "schema_version": "kb.index.bad"}
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path, chunks_path, manifest_path = self._write_runtime_artifacts(
                Path(temp_dir),
                index=bad_index,
            )

            with self.assertRaisesRegex(P6IndexLoadError, "index schema mismatch"):
                load_p6_runtime_index(
                    index_path=index_path,
                    chunks_path=chunks_path,
                    source_manifest_path=manifest_path,
                )

    def test_chunk_hash_mismatch_fails_closed(self) -> None:
        bad_chunks = [dict(chunk) for chunk in self.base_chunks]
        bad_chunks[0]["content"] = bad_chunks[0]["content"] + "\nModified after indexing."
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path, chunks_path, manifest_path = self._write_runtime_artifacts(
                Path(temp_dir),
                chunks=bad_chunks,
            )

            with self.assertRaisesRegex(P6IndexLoadError, "chunk content hash mismatch"):
                load_p6_runtime_index(
                    index_path=index_path,
                    chunks_path=chunks_path,
                    source_manifest_path=manifest_path,
                )

    def test_unapproved_source_chunk_fails_closed(self) -> None:
        bad_chunks = [dict(chunk) for chunk in self.base_chunks]
        bad_chunks[0]["source_id"] = "synthetic_smoke_001"
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path, chunks_path, manifest_path = self._write_runtime_artifacts(
                Path(temp_dir),
                chunks=bad_chunks,
            )

            with self.assertRaisesRegex(P6IndexLoadError, "not approved for P6 runtime"):
                load_p6_runtime_index(
                    index_path=index_path,
                    chunks_path=chunks_path,
                    source_manifest_path=manifest_path,
                )


if __name__ == "__main__":
    unittest.main()

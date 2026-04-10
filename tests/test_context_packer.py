"""Tests for Context Packer module."""
import json
import unittest
from pathlib import Path

from obsidian_bridge.context_packer import (
    SKIP_DIRS,
    SKIP_EXTS,
    ProjectPacker,
    _estimate_tokens,
    _truncate,
)


class TestTruncate(unittest.TestCase):
    """Test content truncation."""

    def test_short_content_unchanged(self):
        content = "line1\nline2\nline3"
        result = _truncate(content, max_lines=10)
        self.assertEqual(result, content)

    def test_long_content_truncated(self):
        lines = [f"line {i}" for i in range(100)]
        content = "\n".join(lines)
        result = _truncate(content, max_lines=10)
        self.assertIn("line 0", result)
        self.assertIn("lines omitted", result)
        self.assertIn("line 99", result)

    def test_keeps_head_and_tail(self):
        lines = [f"L{i}" for i in range(50)]
        content = "\n".join(lines)
        result = _truncate(content, max_lines=10)
        # Head should have ~6-7 lines, tail ~3-4 lines
        self.assertIn("L0", result)
        self.assertIn("L49", result)


class TestEstimateTokens(unittest.TestCase):
    """Test token estimation."""

    def test_basic_estimate(self):
        # ~4 chars per token
        text = "A" * 400
        tokens = _estimate_tokens(text)
        self.assertEqual(tokens, 100)

    def test_empty(self):
        self.assertEqual(_estimate_tokens(""), 0)


class TestProjectPacker(unittest.TestCase):
    """Test project packing."""

    def setUp(self):
        self.test_dir = Path("/tmp/test_packer_project")
        if self.test_dir.exists():
            import shutil
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True)

        # Create minimal project structure
        (self.test_dir / "package.json").write_text(json.dumps({
            "name": "test-project",
            "dependencies": {"next": "14.0.0", "@prisma/client": "5.0.0"}
        }))
        (self.test_dir / "tsconfig.json").write_text("{}")
        (self.test_dir / "README.md").write_text("# Test Project\nA test.")

        # Source files
        src = self.test_dir / "src"
        src.mkdir()
        (src / "index.ts").write_text("export function main() { return 1; }")
        (src / "utils.ts").write_text("export function add(a: number, b: number) { return a + b; }")

        # File that should be skipped
        (self.test_dir / "image.png").write_bytes(b"\x89PNG")
        nm = self.test_dir / "node_modules"
        nm.mkdir()
        (nm / "thing.js").write_text("module.exports = 1;")

    def tearDown(self):
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_detect_stack(self):
        packer = ProjectPacker(self.test_dir)
        stack = packer._detect_stack()
        self.assertIn("Node.js", stack)
        self.assertIn("TypeScript", stack)
        self.assertIn("Next.js", stack)
        self.assertIn("Prisma", stack)

    def test_discover_files_skips_dirs(self):
        packer = ProjectPacker(self.test_dir)
        files = packer._discover_files()
        paths = [str(f) for f in files]
        # Should include source files
        self.assertTrue(any("index.ts" in p for p in paths))
        # Should NOT include node_modules
        self.assertFalse(any("node_modules" in p for p in paths))
        # Should NOT include images
        self.assertFalse(any(".png" in p for p in paths))

    def test_pack_compact(self):
        packer = ProjectPacker(self.test_dir, mode="compact")
        ctx = packer.pack()
        self.assertGreater(ctx.included_files, 0)
        self.assertEqual(ctx.name, "test_packer_project")
        self.assertIn("Node.js", ctx.stack)

    def test_pack_minimal(self):
        packer = ProjectPacker(self.test_dir, mode="minimal")
        ctx = packer.pack()
        self.assertGreater(ctx.included_files, 0)
        self.assertLessEqual(ctx.token_estimate, 15_000)

    def test_to_markdown(self):
        packer = ProjectPacker(self.test_dir, mode="minimal")
        ctx = packer.pack()
        md = packer.to_markdown(ctx)
        self.assertIn("Project Context: test_packer_project", md)
        self.assertIn("Stack", md)
        self.assertIn("File Tree", md)
        self.assertIn("Source Files", md)

    def test_classify_priority(self):
        packer = ProjectPacker(self.test_dir)
        files = packer._discover_files()
        classified = packer._classify(files)

        # package.json should be high priority
        high_files = [str(f) for f, p in classified if p == "high"]
        self.assertTrue(any("package.json" in f for f in high_files))


class TestSkipPatterns(unittest.TestCase):
    """Test that skip patterns are comprehensive."""

    def test_common_dirs_skipped(self):
        self.assertIn("node_modules", SKIP_DIRS)
        self.assertIn(".git", SKIP_DIRS)
        self.assertIn("__pycache__", SKIP_DIRS)
        self.assertIn(".venv", SKIP_DIRS)
        self.assertIn(".next", SKIP_DIRS)

    def test_binary_exts_skipped(self):
        self.assertIn(".png", SKIP_EXTS)
        self.assertIn(".jpg", SKIP_EXTS)
        self.assertIn(".mp4", SKIP_EXTS)
        self.assertIn(".zip", SKIP_EXTS)
        self.assertIn(".pyc", SKIP_EXTS)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from controllers.DataController import DataController
from controllers.ProcessController import Document, ProcessController
from controllers.ProjectController import ProjectController


class FakeUpload:
    def __init__(self, content_type: str, size: int, filename: str = "file.txt"):
        self.content_type = content_type
        self.size = size
        self.filename = filename


def test_validate_uploaded_file_accepts_allowed_type(
    test_settings: SimpleNamespace,
):
    controller = DataController()

    is_valid, signal = controller.validate_uploaded_file(
        FakeUpload("text/plain", size=10)
    )

    assert is_valid is True
    assert signal == "file_uploaded_successfully"


def test_validate_uploaded_file_rejects_unknown_type(
    test_settings: SimpleNamespace,
):
    controller = DataController()

    is_valid, signal = controller.validate_uploaded_file(
        FakeUpload("application/zip", size=1)
    )

    assert is_valid is False
    assert signal == "file_type_not_supported"


def test_validate_uploaded_file_rejects_files_over_limit(
    test_settings: SimpleNamespace,
):
    controller = DataController()
    # FILE_MAX_SIZE is expressed in MiB by DataController.
    too_large = (test_settings.FILE_MAX_SIZE * controller.size_scale) + 1

    is_valid, signal = controller.validate_uploaded_file(
        FakeUpload("application/pdf", size=too_large)
    )

    assert is_valid is False
    assert signal == "file_size_exceeded"


def test_validate_uploaded_file_accepts_file_at_limit(
    test_settings: SimpleNamespace,
):
    controller = DataController()
    max_size = test_settings.FILE_MAX_SIZE * controller.size_scale

    is_valid, signal = controller.validate_uploaded_file(
        FakeUpload("text/plain", size=max_size)
    )

    assert is_valid is True
    assert signal == "file_uploaded_successfully"


def test_get_clean_filename_removes_unsafe_characters(
    test_settings: SimpleNamespace,
):
    controller = DataController()

    cleaned = controller.get_clean_filename("  quarterly report (final).txt  ")

    assert cleaned == "quarterlyreportfinal.txt"
    assert "/" not in cleaned
    assert "\\" not in cleaned


def test_generate_unique_filepath_avoids_an_existing_name(
    test_settings: SimpleNamespace,
    isolated_project_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    controller = DataController()
    keys = iter(["first", "second"])
    monkeypatch.setattr(
        controller,
        "generate_random_string",
        lambda length=12: next(keys),
    )

    first_path = isolated_project_path / "first_report.txt"
    first_path.write_text("existing")

    path, filename = controller.generate_unique_filepath(
        original_name="report.txt",
        project_id="1",
    )

    assert Path(path) == isolated_project_path / "second_report.txt"
    assert filename == "second_report.txt"


def test_project_path_is_created_under_configured_files_directory(
    test_settings: SimpleNamespace,
    tmp_path: Path,
):
    controller = ProjectController()
    controller.files_dir = str(tmp_path)

    path = Path(controller.get_project_path(42))

    assert path == tmp_path / "42"
    assert path.is_dir()


def test_database_path_is_created_under_configured_database_directory(
    test_settings: SimpleNamespace,
    tmp_path: Path,
):
    from controllers.BaseController import BaseController

    controller = BaseController()
    controller.database_dir = str(tmp_path)

    path = Path(controller.get_database_path("vector_store"))

    assert path == tmp_path / "vector_store"
    assert path.is_dir()


def test_process_file_loader_decodes_content_and_preserves_source(
    test_settings: SimpleNamespace,
    isolated_project_path: Path,
):
    controller = ProcessController(project_id="1")

    documents = controller.get_file_loader(
        b"Hello, RAG!\nSecond line.",
        source="documents/notes.txt",
    )

    assert len(documents) == 1
    assert documents[0].page_content == "Hello, RAG!\nSecond line."
    assert documents[0].metadata == {"source": "documents/notes.txt"}


def test_process_simpler_splitter_groups_lines_into_chunks(
    test_settings: SimpleNamespace,
    isolated_project_path: Path,
):
    controller = ProcessController(project_id="1")

    chunks = controller.process_simpler_splitter(
        texts=["first line\nsecond line\nthird", "fourth"],
        metadatas=[{"source": "a"}, {"source": "b"}],
        chunk_size=12,
    )

    assert [chunk.page_content for chunk in chunks] == [
        "first line\nsecond line",
        "third fourth",
    ]
    assert all(isinstance(chunk, Document) for chunk in chunks)


def test_process_file_content_returns_no_chunks_for_empty_input(
    test_settings: SimpleNamespace,
    isolated_project_path: Path,
):
    controller = ProcessController(project_id="1")

    assert controller.process_file_content([]) == []


def test_process_file_content_splits_documents_using_chunk_size(
    test_settings: SimpleNamespace,
    isolated_project_path: Path,
):
    controller = ProcessController(project_id="1")
    documents = [
        Document(
            page_content="alpha\nbeta\ngamma",
            metadata={"source": "notes.txt"},
        )
    ]

    chunks = controller.process_file_content(
        file_content=documents,
        chunk_size=5,
        overlap_size=2,
    )

    assert [chunk.page_content for chunk in chunks] == [
        "alpha",
        "beta",
        "gamma",
    ]


def test_get_file_extension_returns_suffix_including_dot(
    test_settings: SimpleNamespace,
    isolated_project_path: Path,
):
    controller = ProcessController(project_id="1")

    assert controller.get_file_extension("document.txt") == ".txt"
    assert controller.get_file_extension("document") == ""

"""SubjectsPage UI 测试：删除弹确认框。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from neuropilot.infra.db.repositories.subject_repo import SubjectDTO, SubjectRepo


def _make_subject(sid: int = 1, name: str = "Alice") -> SubjectDTO:
    return SubjectDTO(
        id=sid, name=name, gender="F", age=30,
        diagnosis="stroke", notes=None,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


@pytest.fixture()
def mock_repo():
    repo = MagicMock(spec=SubjectRepo)
    subject = _make_subject()
    repo.list.return_value = [subject]
    repo.get.return_value = subject
    return repo


@pytest.mark.qt
def test_delete_shows_confirm_dialog(qtbot, mock_repo):
    from neuropilot.ui.pages.subjects_page import SubjectsPage

    page = SubjectsPage(mock_repo)
    qtbot.addWidget(page)

    page._table.selectRow(0)
    page._on_selection_changed()

    with patch("neuropilot.ui.pages.subjects_page.MessageBox") as MockBox:
        instance = MockBox.return_value
        instance.exec_.return_value = False  # 用户取消
        page._on_delete()

        MockBox.assert_called_once()
        mock_repo.delete.assert_not_called()


@pytest.mark.qt
def test_delete_confirmed(qtbot, mock_repo):
    from neuropilot.ui.pages.subjects_page import SubjectsPage

    page = SubjectsPage(mock_repo)
    qtbot.addWidget(page)

    page._table.selectRow(0)
    page._on_selection_changed()

    with patch("neuropilot.ui.pages.subjects_page.MessageBox") as MockBox:
        instance = MockBox.return_value
        instance.exec_.return_value = True  # 用户确认
        page._on_delete()

        mock_repo.delete.assert_called_once_with(1)

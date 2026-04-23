from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    LineEdit,
    MessageBox,
    PrimaryPushButton,
    PushButton,
    SearchLineEdit,
    SubtitleLabel,
)

from neuropilot.app.event_bus import EventBus
from neuropilot.infra.db.repositories.subject_repo import (
    SubjectCreateDTO,
    SubjectDTO,
    SubjectRepo,
    SubjectUpdateDTO,
)


class SubjectsPage(QWidget):
    def __init__(self, subject_repo: SubjectRepo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._repo = subject_repo
        self._selected_id: Optional[int] = None
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        layout.addWidget(SubtitleLabel("受试者管理", self))

        top_row = QHBoxLayout()
        self._search = SearchLineEdit(self)
        self._search.setPlaceholderText("按姓名搜索")
        self._search.textChanged.connect(self._refresh)
        top_row.addWidget(self._search, 1)

        add_btn = PrimaryPushButton("新建受试者", self)
        add_btn.clicked.connect(self._on_add)
        top_row.addWidget(add_btn)
        layout.addLayout(top_row)

        self._table = QTableWidget(0, 6, self)
        self._table.setHorizontalHeaderLabels(["ID", "姓名", "性别", "年龄", "诊断", "备注"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)  # type: ignore[attr-defined]
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)  # type: ignore[attr-defined]
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)  # type: ignore[attr-defined]
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._table, 1)

        btn_row = QHBoxLayout()
        self._edit_btn = PushButton("编辑", self)
        self._edit_btn.setEnabled(False)
        self._edit_btn.clicked.connect(self._on_edit)
        self._del_btn = PushButton("删除", self)
        self._del_btn.setEnabled(False)
        self._del_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self._edit_btn)
        btn_row.addWidget(self._del_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _refresh(self) -> None:
        keyword = self._search.text().strip() if hasattr(self, "_search") else ""
        subjects = self._repo.list(keyword=keyword)
        self._table.setRowCount(len(subjects))
        for row, subject in enumerate(subjects):
            self._table.setItem(row, 0, QTableWidgetItem(str(subject.id)))
            self._table.setItem(row, 1, QTableWidgetItem(subject.name))
            self._table.setItem(row, 2, QTableWidgetItem(subject.gender or ""))
            self._table.setItem(row, 3, QTableWidgetItem("" if subject.age is None else str(subject.age)))
            self._table.setItem(row, 4, QTableWidgetItem(subject.diagnosis or ""))
            self._table.setItem(row, 5, QTableWidgetItem(subject.notes or ""))

    def _on_selection_changed(self) -> None:
        selected = self._table.selectedItems()
        has_selection = len(selected) > 0
        self._edit_btn.setEnabled(has_selection)
        self._del_btn.setEnabled(has_selection)
        if not has_selection:
            self._selected_id = None
            return

        row = self._table.currentRow()
        item = self._table.item(row, 0)
        self._selected_id = int(item.text()) if item is not None else None
        if self._selected_id is None:
            return

        subject = self._repo.get(self._selected_id)
        if subject is not None:
            EventBus.instance().subject_selected.emit(subject)

    def _on_add(self) -> None:
        dialog = _SubjectFormDialog(self)
        if dialog.exec_():
            dto = dialog.to_create_dto()
            if dto is not None:
                self._repo.create(dto)
                EventBus.instance().subject_changed.emit()
                self._refresh()

    def _on_edit(self) -> None:
        if self._selected_id is None:
            return
        subject = self._repo.get(self._selected_id)
        if subject is None:
            return
        dialog = _SubjectFormDialog(self, subject)
        if dialog.exec_():
            dto = dialog.to_update_dto()
            if dto is not None:
                self._repo.update(self._selected_id, dto)
                EventBus.instance().subject_changed.emit()
                self._refresh()

    def _on_delete(self) -> None:
        if self._selected_id is None:
            return
        subject = self._repo.get(self._selected_id)
        if subject is None:
            return

        dialog = MessageBox(
            "删除受试者",
            f"此操作将永久删除受试者「{subject.name}」及相关数据。\n\n是否继续？",
            self,
        )
        if dialog.exec_():
            self._repo.delete(self._selected_id)
            self._selected_id = None
            EventBus.instance().subject_changed.emit()
            self._refresh()


class _SubjectFormDialog(MessageBox):
    def __init__(self, parent: QWidget, subject: SubjectDTO | None = None) -> None:
        title = "编辑受试者" if subject else "新建受试者"
        super().__init__(title, "", parent)
        self._subject = subject
        self._build_form()
        if subject is not None:
            self._populate(subject)

    def _build_form(self) -> None:
        form_widget = QWidget(self)
        form = QFormLayout(form_widget)
        form.setSpacing(8)

        self._name_edit = LineEdit(form_widget)
        self._name_edit.setPlaceholderText("必填")
        form.addRow(BodyLabel("姓名 *"), self._name_edit)

        self._gender_edit = LineEdit(form_widget)
        self._gender_edit.setPlaceholderText("男 / 女 / 其他")
        form.addRow(BodyLabel("性别"), self._gender_edit)

        self._age_edit = LineEdit(form_widget)
        self._age_edit.setPlaceholderText("数字")
        form.addRow(BodyLabel("年龄"), self._age_edit)

        self._diag_edit = LineEdit(form_widget)
        form.addRow(BodyLabel("诊断"), self._diag_edit)

        self._notes_edit = LineEdit(form_widget)
        form.addRow(BodyLabel("备注"), self._notes_edit)

        self.textLayout.addWidget(form_widget)

    def _populate(self, subject: SubjectDTO) -> None:
        self._name_edit.setText(subject.name)
        self._gender_edit.setText(subject.gender or "")
        self._age_edit.setText("" if subject.age is None else str(subject.age))
        self._diag_edit.setText(subject.diagnosis or "")
        self._notes_edit.setText(subject.notes or "")

    def to_create_dto(self) -> Optional[SubjectCreateDTO]:
        name = self._name_edit.text().strip()
        if not name:
            return None
        return SubjectCreateDTO(
            name=name,
            gender=self._gender_edit.text().strip() or None,
            age=int(self._age_edit.text()) if self._age_edit.text().strip().isdigit() else None,
            diagnosis=self._diag_edit.text().strip() or None,
            notes=self._notes_edit.text().strip() or None,
        )

    def to_update_dto(self) -> Optional[SubjectUpdateDTO]:
        name = self._name_edit.text().strip()
        if not name:
            return None
        return SubjectUpdateDTO(
            name=name,
            gender=self._gender_edit.text().strip() or None,
            age=int(self._age_edit.text()) if self._age_edit.text().strip().isdigit() else None,
            diagnosis=self._diag_edit.text().strip() or None,
            notes=self._notes_edit.text().strip() or None,
        )

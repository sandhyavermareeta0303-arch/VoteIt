import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import db
from .export import export_results_to_excel
from .paths import ensure_app_dirs


class VotingDialog(QDialog):
    def __init__(self, election_id: int, election_label: str, session_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.election_id = election_id
        self.session_id = session_id
        self.pending_votes: dict[int, int] = {}
        self.candidate_buttons: dict[int, QPushButton] = {}

        self.setWindowTitle(f"Voting - {election_label}")
        self.setModal(False)

        layout = QVBoxLayout(self)
        title = QLabel(election_label)
        title.setObjectName("voterTitle")
        status = QLabel("Voting enabled.")
        status.setObjectName("status")
        self.vote_status = status
        layout.addWidget(title)
        layout.addWidget(status)

        action_row = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        self.submit_button = QPushButton("Submit Vote")
        self.submit_button.setObjectName("primaryAction")
        self.submit_button.clicked.connect(self.submit_vote)
        action_row.addStretch(1)
        action_row.addWidget(self.cancel_button)
        action_row.addWidget(self.submit_button)
        layout.addLayout(action_row)

        self.vote_scroll = QScrollArea()
        self.vote_scroll.setWidgetResizable(True)
        self.vote_container = QWidget()
        self.vote_layout = QVBoxLayout(self.vote_container)
        self.vote_scroll.setWidget(self.vote_container)
        layout.addWidget(self.vote_scroll, 1)

        self.render_voting_screen()
        self.fit_to_screen()

    def render_voting_screen(self) -> None:
        self.clear_layout(self.vote_layout)
        self.candidate_buttons = {}
        polls = db.list_polls(self.election_id)
        for poll in polls:
            candidates = db.list_candidates(poll["id"])
            if not candidates:
                continue
            box = QGroupBox(poll["name"])
            grid = QGridLayout(box)
            for index, candidate in enumerate(candidates):
                card = self.build_candidate_card(poll["id"], candidate)
                grid.addWidget(card, index // 3, index % 3)
            self.vote_layout.addWidget(box)
        self.vote_layout.addStretch(1)

    def fit_to_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if not screen:
            self.resize(980, 640)
            return
        available = screen.availableGeometry()
        width = min(1040, max(760, int(available.width() * 0.9)))
        height = min(640, max(480, int(available.height() * 0.82)))
        self.resize(width, height)
        self.move(
            available.x() + (available.width() - width) // 2,
            available.y() + (available.height() - height) // 2,
        )

    def build_candidate_card(self, poll_id: int, candidate: dict) -> QFrame:
        card = QFrame()
        card.setObjectName("candidateCard")
        layout = QVBoxLayout(card)
        image = QLabel()
        image.setObjectName("candidatePhoto")
        image.setAlignment(Qt.AlignCenter)
        image.setFixedSize(150, 112)
        photo_path = candidate["photo_path"]
        if photo_path and Path(photo_path).exists():
            pixmap = QPixmap(photo_path).scaled(150, 112, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            image.setPixmap(pixmap)
        else:
            image.setText("No Photo")
        name = QLabel(candidate["name"])
        name.setObjectName("candidateName")
        name.setWordWrap(True)
        desc = QLabel(candidate["description"])
        desc.setWordWrap(True)
        desc.setObjectName("candidateDesc")
        button = QPushButton("Vote")
        button.clicked.connect(lambda: self.select_candidate(poll_id, candidate["id"]))
        self.candidate_buttons[candidate["id"]] = button
        layout.addWidget(image, alignment=Qt.AlignCenter)
        layout.addWidget(name)
        layout.addWidget(desc)
        layout.addStretch(1)
        layout.addWidget(button)
        return card

    def select_candidate(self, poll_id: int, candidate_id: int) -> None:
        self.pending_votes[poll_id] = candidate_id
        for candidate in db.list_candidates(poll_id):
            button = self.candidate_buttons.get(candidate["id"])
            if button:
                button.setEnabled(False)
                button.setText("Selected" if candidate["id"] == candidate_id else "Disabled")
        selected = len(self.pending_votes)
        required = len(self.required_poll_ids())
        self.vote_status.setText(f"Selected {selected} of {required} poll(s).")

    def submit_vote(self) -> None:
        required_poll_ids = self.required_poll_ids()
        if required_poll_ids and set(self.pending_votes) != required_poll_ids:
            QMessageBox.warning(self, "VoteIt", "Please select one candidate in each poll before submitting.")
            return
        try:
            db.cast_votes(self.election_id, list(self.pending_votes.items()), self.session_id)
        except ValueError as exc:
            QMessageBox.warning(self, "VoteIt", str(exc))
            self.reject()
            return
        QMessageBox.information(self, "Vote Saved", "Vote recorded successfully.")
        self.accept()

    def required_poll_ids(self) -> set[int]:
        polls = db.list_polls(self.election_id)
        return {poll["id"] for poll in polls if db.list_candidates(poll["id"])}

    def clear_layout(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget:
                widget.deleteLater()
            elif child_layout:
                self.clear_layout(child_layout)


class VoteItWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VoteIt - School Voting System")
        self.resize(1180, 760)
        self.voting_window: VotingDialog | None = None
        self.photo_source = ""

        root = QWidget()
        layout = QVBoxLayout(root)
        title = QLabel("VoteIt")
        title.setObjectName("appTitle")
        subtitle = QLabel("Offline operator-controlled voting system")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.build_setup_tab(), "Setup")
        self.tabs.addTab(self.build_voting_tab(), "Voting")
        self.tabs.addTab(self.build_results_tab(), "Results")
        layout.addWidget(self.tabs)
        self.setCentralWidget(root)
        self.apply_styles()
        self.refresh_all()

    def build_setup_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)

        election_box = QGroupBox("Elections")
        election_layout = QVBoxLayout(election_box)
        self.election_list = QListWidget()
        self.election_name = QLineEdit()
        self.election_name.setPlaceholderText("Election name")
        self.election_desc = QTextEdit()
        self.election_desc.setPlaceholderText("Description")
        self.election_desc.setFixedHeight(72)
        add_election = QPushButton("Create Election")
        add_election.clicked.connect(self.create_election)
        activate_election = QPushButton("Start Election")
        activate_election.clicked.connect(lambda: self.set_election_status("active"))
        close_election = QPushButton("Close Election")
        close_election.clicked.connect(lambda: self.set_election_status("closed"))
        election_layout.addWidget(self.election_list)
        election_layout.addWidget(self.election_name)
        election_layout.addWidget(self.election_desc)
        election_layout.addWidget(add_election)
        election_layout.addWidget(activate_election)
        election_layout.addWidget(close_election)

        poll_box = QGroupBox("Polls")
        poll_layout = QVBoxLayout(poll_box)
        self.setup_election_combo = QComboBox()
        self.poll_name = QLineEdit()
        self.poll_name.setPlaceholderText("Poll name, e.g. School Captain Boys")
        add_poll = QPushButton("Create Poll")
        add_poll.clicked.connect(self.create_poll)
        self.poll_list = QListWidget()
        poll_layout.addWidget(QLabel("Election"))
        poll_layout.addWidget(self.setup_election_combo)
        self.setup_status = QLabel("")
        self.setup_status.setObjectName("status")
        poll_layout.addWidget(self.setup_status)
        poll_layout.addWidget(self.poll_name)
        self.add_poll_button = add_poll
        poll_layout.addWidget(self.add_poll_button)
        poll_layout.addWidget(self.poll_list)

        candidate_box = QGroupBox("Candidates")
        candidate_layout = QVBoxLayout(candidate_box)
        self.candidate_poll_combo = QComboBox()
        self.candidate_name = QLineEdit()
        self.candidate_name.setPlaceholderText("Candidate name")
        self.candidate_desc = QTextEdit()
        self.candidate_desc.setPlaceholderText("Class, house, notes, or description")
        self.candidate_desc.setFixedHeight(86)
        photo_row = QHBoxLayout()
        self.photo_label = QLabel("No photo selected")
        choose_photo = QPushButton("Choose Photo")
        choose_photo.clicked.connect(self.choose_photo)
        photo_row.addWidget(self.photo_label, 1)
        photo_row.addWidget(choose_photo)
        add_candidate = QPushButton("Add Candidate")
        add_candidate.clicked.connect(self.create_candidate)
        self.candidate_list = QListWidget()
        candidate_layout.addWidget(QLabel("Poll"))
        candidate_layout.addWidget(self.candidate_poll_combo)
        candidate_layout.addWidget(self.candidate_name)
        candidate_layout.addWidget(self.candidate_desc)
        candidate_layout.addLayout(photo_row)
        self.add_candidate_button = add_candidate
        candidate_layout.addWidget(self.add_candidate_button)
        candidate_layout.addWidget(self.candidate_list)

        layout.addWidget(election_box, 1)
        layout.addWidget(poll_box, 1)
        layout.addWidget(candidate_box, 1)
        self.setup_election_combo.currentIndexChanged.connect(self.refresh_setup_dependents)
        self.candidate_poll_combo.currentIndexChanged.connect(self.refresh_candidates)
        return page

    def build_voting_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        self.vote_election_combo = QComboBox()
        self.operator_name = QLineEdit()
        self.operator_name.setPlaceholderText("Operator name")
        self.enable_button = QPushButton("Open Voter Window")
        self.enable_button.clicked.connect(self.enable_voting)
        self.lock_button = QPushButton("Close Voter Window")
        self.lock_button.clicked.connect(self.lock_voting)
        change_password = QPushButton("Change Password")
        change_password.clicked.connect(self.change_operator_password)
        top.addWidget(QLabel("Election"))
        top.addWidget(self.vote_election_combo, 1)
        top.addWidget(self.operator_name)
        top.addWidget(self.enable_button)
        top.addWidget(self.lock_button)
        top.addWidget(change_password)
        layout.addLayout(top)

        self.vote_status = QLabel("Ready. Select an active election to open the voter window.")
        self.vote_status.setObjectName("status")
        layout.addWidget(self.vote_status)

        info_box = QGroupBox("Operator Console")
        info_layout = QVBoxLayout(info_box)
        self.vote_summary = QLabel("")
        self.vote_summary.setWordWrap(True)
        info_layout.addWidget(self.vote_summary)
        layout.addWidget(info_box)
        layout.addStretch(1)
        self.vote_election_combo.currentIndexChanged.connect(self.update_voting_summary)
        return page

    def build_results_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        self.result_election_combo = QComboBox()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_results)
        export = QPushButton("Export Excel")
        export.clicked.connect(self.export_results)
        top.addWidget(QLabel("Election"))
        top.addWidget(self.result_election_combo, 1)
        top.addWidget(refresh)
        top.addWidget(export)
        layout.addLayout(top)

        self.result_list = QListWidget()
        layout.addWidget(self.result_list, 1)
        self.result_election_combo.currentIndexChanged.connect(self.refresh_results)
        return page

    def refresh_all(self) -> None:
        self.refresh_elections()
        self.refresh_setup_dependents()
        self.update_voting_summary()
        self.refresh_results()

    def refresh_elections(self) -> None:
        elections = db.list_elections()
        self.election_list.clear()
        for election in elections:
            self.election_list.addItem(
                f"{election['name']}  [{self.status_label(election['status'])}]  {election['created_at']}"
            )
        for combo in (self.setup_election_combo, self.vote_election_combo, self.result_election_combo):
            current_id = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for election in elections:
                combo.addItem(f"{election['name']} [{self.status_label(election['status'])}]", election["id"])
            if current_id:
                index = combo.findData(current_id)
                if index >= 0:
                    combo.setCurrentIndex(index)
            combo.blockSignals(False)

    def refresh_setup_dependents(self) -> None:
        election_id = self.setup_election_combo.currentData()
        self.poll_list.clear()
        self.candidate_poll_combo.blockSignals(True)
        self.candidate_poll_combo.clear()
        setup_open = False
        if election_id:
            election = db.get_election(election_id)
            setup_open = bool(election and election["status"] == "draft")
            for poll in db.list_polls(election_id):
                self.poll_list.addItem(poll["name"])
                self.candidate_poll_combo.addItem(poll["name"], poll["id"])
            status = self.status_label(election["status"]) if election else "Missing"
            self.setup_status.setText(f"Setup: {'Open' if setup_open else 'Locked'} | Election: {status}")
        else:
            self.setup_status.setText("Setup: No election selected")
        self.poll_name.setEnabled(setup_open)
        self.add_poll_button.setEnabled(setup_open)
        self.candidate_name.setEnabled(setup_open)
        self.candidate_desc.setEnabled(setup_open)
        self.add_candidate_button.setEnabled(setup_open and self.candidate_poll_combo.count() > 0)
        self.candidate_poll_combo.blockSignals(False)
        self.refresh_candidates()

    def refresh_candidates(self) -> None:
        poll_id = self.candidate_poll_combo.currentData()
        self.candidate_list.clear()
        setup_open = False
        election_id = self.setup_election_combo.currentData()
        if election_id:
            setup_open = db.get_election_status(election_id) == "draft"
        self.add_candidate_button.setEnabled(setup_open and bool(poll_id))
        if not poll_id:
            return
        for candidate in db.list_candidates(poll_id):
            photo_note = "photo" if candidate["photo_path"] else "no photo"
            self.candidate_list.addItem(f"{candidate['name']} - {photo_note}")

    def create_election(self) -> None:
        name = self.election_name.text().strip()
        if not name:
            self.warn("Election name is required.")
            return
        try:
            db.create_election(name, self.election_desc.toPlainText())
        except Exception as exc:
            self.warn(f"Could not create election: {exc}")
            return
        self.election_name.clear()
        self.election_desc.clear()
        self.refresh_all()

    def set_election_status(self, status: str) -> None:
        election_id = self.setup_election_combo.currentData()
        if not election_id:
            self.warn("Create or select an election first.")
            return
        if status == "active":
            polls = db.list_polls(election_id)
            if not polls:
                self.warn("Add at least one poll before starting the election.")
                return
            empty_polls = [poll["name"] for poll in polls if not db.list_candidates(poll["id"])]
            if empty_polls:
                self.warn(f"Add candidates before starting. Empty poll: {empty_polls[0]}")
                return
        if status == "closed":
            answer = QMessageBox.question(
                self,
                "Close Election",
                "Close this election? Voting will stop immediately.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        db.update_election_status(election_id, status)
        if status == "closed" and self.voting_window and self.voting_window.election_id == election_id:
            self.voting_window.reject()
        self.refresh_all()

    def create_poll(self) -> None:
        election_id = self.setup_election_combo.currentData()
        name = self.poll_name.text().strip()
        if not election_id or not name:
            self.warn("Select an election and enter a poll name.")
            return
        try:
            db.create_poll(election_id, name)
        except Exception as exc:
            self.warn(f"Could not create poll: {exc}")
            return
        self.poll_name.clear()
        self.refresh_all()

    def choose_photo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Candidate Photo",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)",
        )
        if path:
            self.photo_source = path
            self.photo_label.setText(Path(path).name)

    def create_candidate(self) -> None:
        poll_id = self.candidate_poll_combo.currentData()
        name = self.candidate_name.text().strip()
        if not poll_id or not name:
            self.warn("Select a poll and enter a candidate name.")
            return
        try:
            poll = db.get_poll(poll_id)
            if not poll:
                self.warn("Selected poll was not found.")
                return
            db.ensure_election_draft(poll["election_id"])
            temp_id = name.lower().replace(" ", "_")[:24] or "new"
            photo_path = db.copy_photo_to_store(self.photo_source, temp_id)
            db.create_candidate(poll_id, name, self.candidate_desc.toPlainText(), photo_path)
        except Exception as exc:
            self.warn(f"Could not add candidate: {exc}")
            return
        self.candidate_name.clear()
        self.candidate_desc.clear()
        self.photo_source = ""
        self.photo_label.setText("No photo selected")
        self.refresh_all()

    def enable_voting(self) -> None:
        if self.voting_window and self.voting_window.isVisible():
            self.warn("A voting window is already open. Submit or lock it before enabling another voter.")
            return
        election_id = self.vote_election_combo.currentData()
        if not election_id:
            self.warn("Create/select an election first.")
            return
        election = db.get_election(election_id)
        if not election or election["status"] != "active":
            self.warn("Only active elections can accept votes. Start the election before opening the voter window.")
            self.update_voting_summary()
            return
        polls = db.list_polls(election_id)
        if not polls:
            self.warn("This election has no polls yet.")
            return
        if not any(db.list_candidates(poll["id"]) for poll in polls):
            self.warn("Add candidates before enabling voting.")
            return

        password, ok = QInputDialog.getText(
            self,
            "Operator Password",
            "Enter operator password to enable voting:",
            QLineEdit.Password,
        )
        if not ok:
            return
        if not db.verify_operator_password(password):
            self.warn("Incorrect operator password.")
            return

        try:
            session_id = db.start_voting_session(election_id, self.operator_name.text())
        except ValueError as exc:
            self.warn(str(exc))
            self.update_voting_summary()
            return
        election_label = self.vote_election_combo.currentText()
        self.voting_window = VotingDialog(election_id, election_label, session_id, self)
        self.voting_window.finished.connect(self.voting_window_closed)
        self.voting_window.show()
        self.voting_window.raise_()
        self.voting_window.activateWindow()
        self.vote_status.setText("Voter window open. It will lock again after submit or close.")

    def lock_voting(self) -> None:
        if self.voting_window and self.voting_window.isVisible():
            self.voting_window.reject()
        self.vote_status.setText("Voter window closed. Ready for the next voter.")

    def voting_window_closed(self, result: int) -> None:
        self.voting_window = None
        if result == QDialog.Accepted:
            self.vote_status.setText("Vote recorded. Locked for the next voter.")
        else:
            self.vote_status.setText("Voting window closed. Locked for the next voter.")
        self.refresh_results()

    def update_voting_summary(self) -> None:
        election_id = self.vote_election_combo.currentData()
        if not election_id:
            self.enable_button.setEnabled(False)
            self.vote_summary.setText(
                "No election selected."
            )
            return
        election = db.get_election(election_id)
        polls = db.list_polls(election_id)
        candidate_count = sum(len(db.list_candidates(poll["id"])) for poll in polls)
        status = election["status"] if election else "missing"
        is_ready = status == "active" and bool(polls) and candidate_count > 0
        self.enable_button.setEnabled(is_ready)
        self.vote_summary.setText(
            f"Status: {self.status_label(status)}\n"
            f"Polls: {len(polls)}\n"
            f"Candidates: {candidate_count}\n"
            f"Voter window: {'Ready' if is_ready else 'Not ready'}"
        )

    def status_label(self, status: str) -> str:
        labels = {
            "draft": "Draft",
            "active": "Active",
            "closed": "Closed",
        }
        return labels.get(status, status.title())

    def change_operator_password(self) -> None:
        current, ok = QInputDialog.getText(
            self,
            "Current Password",
            "Enter current operator password:",
            QLineEdit.Password,
        )
        if not ok:
            return
        if not db.verify_operator_password(current):
            self.warn("Incorrect current password.")
            return

        new_password, ok = QInputDialog.getText(
            self,
            "New Password",
            "Enter new operator password:",
            QLineEdit.Password,
        )
        if not ok:
            return
        if len(new_password.strip()) < 4:
            self.warn("Use at least 4 characters for the operator password.")
            return

        confirm, ok = QInputDialog.getText(
            self,
            "Confirm Password",
            "Re-enter new operator password:",
            QLineEdit.Password,
        )
        if not ok:
            return
        if new_password != confirm:
            self.warn("New passwords do not match.")
            return

        db.set_operator_password(new_password)
        QMessageBox.information(self, "Password Changed", "Operator password updated successfully.")

    def refresh_results(self) -> None:
        election_id = self.result_election_combo.currentData()
        self.result_list.clear()
        if not election_id:
            return
        rows = db.get_results(election_id)
        current_poll = None
        for row in rows:
            if row["poll_name"] != current_poll:
                current_poll = row["poll_name"]
                header = QListWidgetItem(f"--- {current_poll} ---")
                header.setFlags(Qt.NoItemFlags)
                self.result_list.addItem(header)
            self.result_list.addItem(f"{row['candidate_name']}: {row['votes']} vote(s)")

    def export_results(self) -> None:
        election_id = self.result_election_combo.currentData()
        if not election_id:
            self.warn("Select an election to export.")
            return
        try:
            path = export_results_to_excel(election_id)
        except Exception as exc:
            self.warn(f"Export failed: {exc}")
            return
        QMessageBox.information(self, "Export Complete", f"Excel result saved:\n{path}")

    def warn(self, message: str) -> None:
        QMessageBox.warning(self, "VoteIt", message)

    def clear_layout(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget:
                widget.deleteLater()
            elif child_layout:
                self.clear_layout(child_layout)

    def apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                font-family: Segoe UI, Arial, sans-serif;
                font-size: 13px;
                color: #17202a;
            }
            QMainWindow, QWidget {
                background: #f6f7f9;
            }
            #appTitle {
                font-size: 30px;
                font-weight: 700;
                color: #102a43;
            }
            #voterTitle {
                font-size: 22px;
                font-weight: 700;
                color: #102a43;
            }
            #subtitle {
                color: #5f6c7b;
                margin-bottom: 8px;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #d9dee7;
                border-radius: 6px;
                margin-top: 16px;
                padding: 12px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
            QLineEdit, QTextEdit, QComboBox, QListWidget {
                background: #ffffff;
                border: 1px solid #c8d0dc;
                border-radius: 4px;
                padding: 7px;
            }
            QPushButton {
                background: #1f6feb;
                border: 0;
                border-radius: 4px;
                color: white;
                padding: 9px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #185abc;
            }
            QPushButton:disabled {
                background: #aeb8c6;
            }
            #primaryAction {
                background: #0b7a53;
                min-width: 150px;
            }
            #primaryAction:hover {
                background: #086846;
            }
            #status {
                background: #fff8d6;
                border: 1px solid #f0d36b;
                border-radius: 4px;
                padding: 10px;
                font-weight: 600;
            }
            #candidateCard {
                background: #fbfcfe;
                border: 1px solid #dce3ed;
                border-radius: 6px;
                min-width: 210px;
                max-width: 250px;
            }
            #candidatePhoto {
                background: #e9eef5;
                border: 1px solid #d4dce8;
                border-radius: 4px;
            }
            #candidateName {
                font-size: 17px;
                font-weight: 700;
            }
            #candidateDesc {
                color: #526173;
            }
            """
        )


def main() -> None:
    ensure_app_dirs()
    db.init_db()
    app = QApplication(sys.argv)
    window = VoteItWindow()
    window.show()
    sys.exit(app.exec())

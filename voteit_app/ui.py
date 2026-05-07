import sys
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
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


PHOTO_PLACEHOLDER_TEXT = "No Photo"


def load_pixmap(path: str | None, width: int, height: int) -> QPixmap | None:
    if not path:
        return None
    try:
        if not Path(path).exists():
            return None
    except OSError:
        return None
    pixmap = QPixmap(path)
    if pixmap.isNull():
        return None
    return pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)


class CandidateVoteCard(QFrame):
    def __init__(self, candidate: dict, on_click) -> None:
        super().__init__()
        self.setObjectName("candidateCard")
        self.candidate_id = candidate["id"]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        photo = QLabel()
        photo.setObjectName("candidatePhoto")
        photo.setFixedSize(96, 96)
        photo.setAlignment(Qt.AlignCenter)
        pixmap = load_pixmap(candidate.get("photo_path"), 96, 96)
        if pixmap is not None:
            photo.setPixmap(pixmap)
        else:
            photo.setText(PHOTO_PLACEHOLDER_TEXT)
        layout.addWidget(photo)

        text_box = QVBoxLayout()
        text_box.setSpacing(4)
        name = QLabel(candidate["name"])
        name.setObjectName("candidateName")
        name.setWordWrap(True)
        desc = QLabel(candidate.get("description") or "")
        desc.setObjectName("candidateDesc")
        desc.setWordWrap(True)
        text_box.addWidget(name)
        text_box.addWidget(desc)
        text_box.addStretch(1)

        self.button = QPushButton("Vote")
        self.button.setObjectName("voteButton")
        self.button.clicked.connect(on_click)
        text_box.addWidget(self.button, alignment=Qt.AlignLeft)

        layout.addLayout(text_box, 1)


class CandidateResultCard(QFrame):
    def __init__(self, row: dict, total_votes: int, is_winner: bool) -> None:
        super().__init__()
        self.setObjectName("resultCard")
        if is_winner:
            self.setProperty("winner", True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(14)

        photo = QLabel()
        photo.setObjectName("resultPhoto")
        photo.setFixedSize(86, 86)
        photo.setAlignment(Qt.AlignCenter)
        pixmap = load_pixmap(row.get("candidate_photo"), 86, 86)
        if pixmap is not None:
            photo.setPixmap(pixmap)
        else:
            photo.setText(PHOTO_PLACEHOLDER_TEXT)
        layout.addWidget(photo)

        info = QVBoxLayout()
        info.setSpacing(3)
        name = QLabel(row["candidate_name"])
        name.setObjectName("resultName")
        name.setWordWrap(True)
        desc = QLabel(row.get("candidate_description") or "")
        desc.setObjectName("resultDesc")
        desc.setWordWrap(True)
        info.addWidget(name)
        info.addWidget(desc)
        if is_winner and row["votes"] > 0:
            badge = QLabel("Winner")
            badge.setObjectName("winnerBadge")
            badge.setAlignment(Qt.AlignCenter)
            info.addWidget(badge, alignment=Qt.AlignLeft)
        info.addStretch(1)
        layout.addLayout(info, 1)

        right = QVBoxLayout()
        right.setSpacing(0)
        votes = QLabel(str(row["votes"]))
        votes.setObjectName("voteCount")
        votes.setAlignment(Qt.AlignCenter)
        votes_caption = QLabel("vote(s)")
        votes_caption.setObjectName("voteCaption")
        votes_caption.setAlignment(Qt.AlignCenter)
        share = (row["votes"] / total_votes * 100) if total_votes else 0
        share_label = QLabel(f"{share:.1f}%")
        share_label.setObjectName("voteShare")
        share_label.setAlignment(Qt.AlignCenter)
        right.addWidget(votes)
        right.addWidget(votes_caption)
        right.addWidget(share_label)
        layout.addLayout(right)


class VotingDialog(QDialog):
    def __init__(
        self,
        election_id: int,
        election_label: str,
        session_id: int,
        target_screen_index: int = 0,
        open_maximized: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.election_id = election_id
        self.session_id = session_id
        self.target_screen_index = target_screen_index
        self.open_maximized = open_maximized
        self._maximized_once = False
        self.pending_votes: dict[int, int] = {}
        self.candidate_buttons: dict[int, QPushButton] = {}

        self.setWindowTitle(f"Voting - {election_label}")
        self.setModal(False)
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
            | Qt.WindowSystemMenuHint
            | Qt.WindowTitleHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel(election_label)
        title.setObjectName("voterTitle")
        title.setWordWrap(True)
        self.vote_status = QLabel("Voting enabled.")
        self.vote_status.setObjectName("status")
        layout.addWidget(title)
        layout.addWidget(self.vote_status)

        action_row = QHBoxLayout()
        self.maximize_button = QPushButton("Maximize")
        self.maximize_button.clicked.connect(self.toggle_maximized)
        self.reset_button = QPushButton("Reset Selections")
        self.reset_button.setObjectName("ghostButton")
        self.reset_button.clicked.connect(self.reset_selections)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("ghostButton")
        self.cancel_button.clicked.connect(self.reject)
        self.submit_button = QPushButton("Submit Vote")
        self.submit_button.setObjectName("primaryAction")
        self.submit_button.clicked.connect(self.submit_vote)
        action_row.addWidget(self.maximize_button)
        action_row.addStretch(1)
        action_row.addWidget(self.reset_button)
        action_row.addWidget(self.cancel_button)
        action_row.addWidget(self.submit_button)
        layout.addLayout(action_row)

        self.vote_scroll = QScrollArea()
        self.vote_scroll.setWidgetResizable(True)
        self.vote_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.vote_scroll.setObjectName("voteScroll")
        self.vote_container = QWidget()
        self.polls_row = QHBoxLayout(self.vote_container)
        self.polls_row.setSpacing(14)
        self.polls_row.setContentsMargins(2, 2, 2, 2)
        self.vote_scroll.setWidget(self.vote_container)
        layout.addWidget(self.vote_scroll, 1)

        self.render_voting_screen()
        self.fit_to_screen()

    def render_voting_screen(self) -> None:
        self.clear_layout(self.polls_row)
        self.candidate_buttons = {}
        polls = db.list_polls(self.election_id)

        any_rendered = False
        for poll in polls:
            candidates = db.list_candidates(poll["id"])
            if not candidates:
                continue
            any_rendered = True
            column = QGroupBox(poll["name"])
            column.setObjectName("pollColumn")
            column_layout = QVBoxLayout(column)
            column_layout.setContentsMargins(10, 18, 10, 10)
            column_layout.setSpacing(10)

            inner_scroll = QScrollArea()
            inner_scroll.setObjectName("pollScroll")
            inner_scroll.setWidgetResizable(True)
            inner_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            inner = QWidget()
            inner_layout = QVBoxLayout(inner)
            inner_layout.setSpacing(10)
            inner_layout.setContentsMargins(2, 2, 2, 2)
            for candidate in candidates:
                poll_id = poll["id"]
                candidate_id = candidate["id"]
                # Absorb the `checked` bool that QPushButton.clicked emits — without
                # this, the bool ends up bound to `pid` and the rest of the defaults
                # are kept, breaking selection silently.
                card = CandidateVoteCard(
                    candidate,
                    on_click=(lambda _checked=False, pid=poll_id, cid=candidate_id: self.toggle_candidate(pid, cid)),
                )
                self.candidate_buttons[candidate_id] = card.button
                inner_layout.addWidget(card)
            inner_layout.addStretch(1)
            inner_scroll.setWidget(inner)
            column_layout.addWidget(inner_scroll, 1)

            column.setMinimumWidth(300)
            column.setMaximumWidth(380)
            self.polls_row.addWidget(column)

        if not any_rendered:
            empty = QLabel("This election has no polls with candidates.")
            empty.setObjectName("emptyHint")
            empty.setAlignment(Qt.AlignCenter)
            self.polls_row.addWidget(empty)

        self.polls_row.addStretch(1)

    def fit_to_screen(self) -> None:
        screens = QApplication.screens()
        if not screens:
            self.resize(1100, 720)
            return
        idx = self.target_screen_index if 0 <= self.target_screen_index < len(screens) else 0
        screen = screens[idx]
        available = screen.availableGeometry()
        width = min(1280, max(900, int(available.width() * 0.85)))
        height = min(820, max(600, int(available.height() * 0.85)))
        self.resize(width, height)
        self.move(
            available.x() + (available.width() - width) // 2,
            available.y() + (available.height() - height) // 2,
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.open_maximized and not self._maximized_once:
            self._maximized_once = True
            self.showMaximized()
            self.maximize_button.setText("Restore")

    def toggle_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
            self.maximize_button.setText("Maximize")
        else:
            self.showMaximized()
            self.maximize_button.setText("Restore")

    def toggle_candidate(self, poll_id: int, candidate_id: int) -> None:
        """Click handler: select if not selected, deselect if same candidate
        re-clicked. Re-clicking re-enables the rest of the poll's candidates."""
        if self.pending_votes.get(poll_id) == candidate_id:
            self.pending_votes.pop(poll_id, None)
            self._apply_poll_selection(poll_id, selected_id=None)
        else:
            self.pending_votes[poll_id] = candidate_id
            self._apply_poll_selection(poll_id, selected_id=candidate_id)
        self._update_status()

    def reset_selections(self) -> None:
        """Clear all pending selections and re-enable every candidate button."""
        self.pending_votes.clear()
        for poll in db.list_polls(self.election_id):
            self._apply_poll_selection(poll["id"], selected_id=None)
        self._update_status()

    def _apply_poll_selection(self, poll_id: int, selected_id: int | None) -> None:
        """Update enabled/selected state for every candidate button in a poll.
        selected_id=None means no selection in this poll (everything reset)."""
        for candidate in db.list_candidates(poll_id):
            button = self.candidate_buttons.get(candidate["id"])
            if not button:
                continue
            if selected_id is None:
                button.setEnabled(True)
                button.setText("Vote")
                button.setProperty("selected", False)
            elif candidate["id"] == selected_id:
                button.setEnabled(True)
                button.setText("Selected (click to undo)")
                button.setProperty("selected", True)
            else:
                button.setEnabled(False)
                button.setText("Locked")
                button.setProperty("selected", False)
            button.style().unpolish(button)
            button.style().polish(button)

    def _update_status(self) -> None:
        selected = len(self.pending_votes)
        required = len(self.required_poll_ids())
        if selected == 0:
            self.vote_status.setText("No selections yet.")
        elif selected < required:
            self.vote_status.setText(
                f"Selected {selected} of {required} poll(s). Pick one in each remaining poll, or click a 'Selected' button to change."
            )
        else:
            self.vote_status.setText(
                f"All {required} poll(s) chosen. Click 'Submit Vote' to record, or click a 'Selected' button to change."
            )

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

    def clear_layout(self, layout) -> None:
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
        self.candidate_list.setIconSize(QSize(56, 56))
        self.candidate_list.setObjectName("setupCandidateList")
        self.candidate_list.setSpacing(4)
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

        display_box = QGroupBox("Voter Display (projector / second monitor)")
        display_layout = QHBoxLayout(display_box)
        display_layout.addWidget(QLabel("Display"))
        self.display_combo = QComboBox()
        display_layout.addWidget(self.display_combo, 1)
        self.maximize_check = QCheckBox("Open maximized on selected display")
        display_layout.addWidget(self.maximize_check)
        self.refresh_displays_button = QPushButton("Refresh Displays")
        self.refresh_displays_button.clicked.connect(self.refresh_displays)
        display_layout.addWidget(self.refresh_displays_button)
        layout.addWidget(display_box)

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
        self.display_combo.currentIndexChanged.connect(self.persist_display_choice)
        self.maximize_check.toggled.connect(self.persist_maximize_choice)

        self.refresh_displays()
        self.load_display_preferences()
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

        self.result_summary = QLabel("")
        self.result_summary.setObjectName("resultSummary")
        layout.addWidget(self.result_summary)

        self.result_scroll = QScrollArea()
        self.result_scroll.setObjectName("resultScroll")
        self.result_scroll.setWidgetResizable(True)
        self.result_container = QWidget()
        self.result_layout = QVBoxLayout(self.result_container)
        self.result_layout.setSpacing(14)
        self.result_layout.setContentsMargins(4, 4, 4, 4)
        self.result_scroll.setWidget(self.result_container)
        layout.addWidget(self.result_scroll, 1)

        self.result_election_combo.currentIndexChanged.connect(self.refresh_results)
        return page

    def refresh_displays(self) -> None:
        screens = QApplication.screens()
        current = self.display_combo.currentData()
        self.display_combo.blockSignals(True)
        self.display_combo.clear()
        primary = QApplication.primaryScreen()
        for index, screen in enumerate(screens):
            label = screen.name() or f"Display {index + 1}"
            geom = screen.geometry()
            tag = " (primary)" if screen is primary else ""
            self.display_combo.addItem(
                f"{index + 1}. {label}{tag}  [{geom.width()}x{geom.height()}]",
                index,
            )
        if current is not None:
            i = self.display_combo.findData(current)
            if i >= 0:
                self.display_combo.setCurrentIndex(i)
        self.display_combo.blockSignals(False)

    def load_display_preferences(self) -> None:
        idx_str = db.get_setting("voter_display_index")
        if idx_str is not None:
            try:
                target = int(idx_str)
                i = self.display_combo.findData(target)
                if i >= 0:
                    self.display_combo.blockSignals(True)
                    self.display_combo.setCurrentIndex(i)
                    self.display_combo.blockSignals(False)
            except ValueError:
                pass
        max_str = db.get_setting("voter_open_maximized")
        if max_str is not None:
            self.maximize_check.blockSignals(True)
            self.maximize_check.setChecked(max_str == "1")
            self.maximize_check.blockSignals(False)

    def persist_display_choice(self) -> None:
        idx = self.display_combo.currentData()
        if idx is not None:
            db.set_setting("voter_display_index", str(int(idx)))

    def persist_maximize_choice(self) -> None:
        db.set_setting("voter_open_maximized", "1" if self.maximize_check.isChecked() else "0")

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
            label = candidate["name"]
            description = candidate.get("description") or ""
            if description:
                label = f"{label}\n{description}"
            item = QListWidgetItem(label)
            photo_path = candidate.get("photo_path")
            if photo_path and Path(photo_path).exists():
                item.setIcon(QIcon(photo_path))
            self.candidate_list.addItem(item)

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

        target_screen = self.display_combo.currentData()
        if target_screen is None:
            target_screen = 0
        open_max = self.maximize_check.isChecked()
        election_label = self.vote_election_combo.currentText()
        self.voting_window = VotingDialog(
            election_id,
            election_label,
            session_id,
            target_screen_index=int(target_screen),
            open_maximized=open_max,
            parent=self,
        )
        self.voting_window.finished.connect(self.voting_window_closed)
        self.voting_window.show()
        self.voting_window.raise_()
        self.voting_window.activateWindow()
        self.vote_status.setText(
            "Voter window open. It will lock again after submit or close."
        )

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
            self.vote_summary.setText("No election selected.")
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
        self._clear_layout(self.result_layout)
        if not election_id:
            self.result_summary.setText("Select an election to view results.")
            self.result_layout.addStretch(1)
            return
        rows = db.get_results(election_id)
        if not rows:
            self.result_summary.setText("No candidates yet.")
            self.result_layout.addStretch(1)
            return

        polls_in_order: list[str] = []
        by_poll: dict[str, list[dict]] = {}
        for row in rows:
            if row["poll_name"] not in by_poll:
                polls_in_order.append(row["poll_name"])
                by_poll[row["poll_name"]] = []
            by_poll[row["poll_name"]].append(row)

        total_votes_all = sum(r["votes"] for r in rows)
        self.result_summary.setText(
            f"{len(polls_in_order)} poll(s) | {total_votes_all} total vote(s) recorded"
        )

        for poll_name in polls_in_order:
            poll_rows = by_poll[poll_name]
            total_votes = sum(r["votes"] for r in poll_rows)
            max_votes = max((r["votes"] for r in poll_rows), default=0)
            box = QGroupBox(f"{poll_name}   -   {total_votes} vote(s)")
            box.setObjectName("resultPoll")
            box_layout = QVBoxLayout(box)
            box_layout.setSpacing(8)
            box_layout.setContentsMargins(12, 22, 12, 12)
            for row in poll_rows:
                is_winner = row["votes"] == max_votes and max_votes > 0
                box_layout.addWidget(CandidateResultCard(row, total_votes, is_winner))
            self.result_layout.addWidget(box)

        self.result_layout.addStretch(1)

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

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget:
                widget.deleteLater()
            elif child_layout:
                self._clear_layout(child_layout)

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
                font-size: 24px;
                font-weight: 800;
                color: #102a43;
            }
            #subtitle {
                color: #5f6c7b;
                margin-bottom: 8px;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #d9dee7;
                border-radius: 8px;
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
            #ghostButton {
                background: #ffffff;
                color: #102a43;
                border: 1px solid #c8d0dc;
            }
            #ghostButton:hover {
                background: #eef2f7;
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

            /* Voter dialog */
            #voteScroll, #pollScroll, #resultScroll {
                border: 0;
                background: transparent;
            }
            #pollColumn {
                background: #ffffff;
                border: 1px solid #d9dee7;
                border-radius: 10px;
                margin-top: 12px;
                font-size: 15px;
                font-weight: 700;
                color: #102a43;
            }
            #pollColumn::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
            }
            #candidateCard {
                background: #fbfcfe;
                border: 1px solid #dce3ed;
                border-radius: 10px;
            }
            #candidateCard:hover {
                border: 1px solid #1f6feb;
                background: #ffffff;
            }
            #candidatePhoto {
                background: #e9eef5;
                border: 1px solid #d4dce8;
                border-radius: 6px;
                color: #8893a4;
                font-size: 11px;
            }
            #candidateName {
                font-size: 16px;
                font-weight: 700;
                color: #102a43;
            }
            #candidateDesc {
                color: #526173;
                font-size: 12px;
            }
            #voteButton {
                background: #1f6feb;
                color: white;
                padding: 7px 18px;
                border-radius: 4px;
                font-weight: 700;
                border: 0;
                min-width: 100px;
            }
            #voteButton:hover { background: #185abc; }
            #voteButton:disabled { background: #aeb8c6; color: white; }
            #voteButton[selected="true"] {
                background: #0b7a53;
                color: white;
                min-width: 170px;
            }
            #voteButton[selected="true"]:hover { background: #086846; }
            #emptyHint {
                color: #6b7886;
                padding: 30px;
                font-size: 14px;
            }

            /* Results */
            #resultSummary {
                color: #475569;
                font-weight: 600;
                padding: 4px 2px 8px 2px;
            }
            #resultPoll {
                background: #ffffff;
                border: 1px solid #d9dee7;
                border-radius: 10px;
                margin-top: 18px;
                font-size: 15px;
                font-weight: 700;
                color: #102a43;
            }
            #resultPoll::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
            }
            #resultCard {
                background: #fbfcfe;
                border: 1px solid #dce3ed;
                border-radius: 10px;
            }
            #resultCard[winner="true"] {
                background: #f3fbf7;
                border: 1px solid #0b7a53;
            }
            #resultPhoto {
                background: #e9eef5;
                border: 1px solid #d4dce8;
                border-radius: 6px;
                color: #8893a4;
                font-size: 11px;
            }
            #resultName {
                font-size: 16px;
                font-weight: 700;
                color: #102a43;
            }
            #resultDesc {
                color: #526173;
                font-size: 12px;
            }
            #voteCount {
                font-size: 30px;
                font-weight: 800;
                color: #1f6feb;
                min-width: 70px;
            }
            #voteCaption {
                color: #6b7886;
                font-size: 11px;
            }
            #voteShare {
                color: #102a43;
                font-size: 12px;
                font-weight: 600;
            }
            #winnerBadge {
                background: #0b7a53;
                color: white;
                border-radius: 10px;
                padding: 3px 12px;
                font-size: 11px;
                font-weight: 700;
                max-width: 80px;
            }

            /* Setup candidate list */
            #setupCandidateList::item {
                border-bottom: 1px solid #eef2f7;
                padding: 6px;
            }
            #setupCandidateList::item:selected {
                background: #e8f0fe;
                color: #102a43;
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

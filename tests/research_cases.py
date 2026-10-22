"""Behaviour of notes and theses, shared by SQLite and PostgreSQL.

The test modules supply a ``session`` fixture. These methods do not
open a database of their own, except through that fixture.
"""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.models.database_models import (
    CompanyDB,
    FinancialMetricsDB,
    NoteDB,
    ThesisDB,
)
from app.models.research import (
    NOTE_BODY_MAX,
    THESIS_BODY_MAX,
    THESIS_BREAKERS_MAX,
    THESIS_TITLE_MAX,
    NoteCreate,
    NoteUpdate,
    ThesisCreate,
    ThesisStatus,
    ThesisUpdate,
)
from app.repositories.company_errors import CompanyNotFoundError
from app.repositories.company_repository import CompanyRepository
from app.repositories.note_repository import NoteRepository
from app.repositories.research_store import ResearchStorageError
from app.repositories.thesis_repository import ThesisRepository
from app.validation.text import TextValidationError


def _text_failure(caught, field):
    """The TextValidationError Pydantic stored for one field."""
    error = caught.value.errors()[0]
    assert error["loc"] == (field,)
    assert error["type"] == "value_error"
    cause = error["ctx"]["error"]
    assert isinstance(cause, TextValidationError)
    assert cause.field == field
    return cause


def _assert_string_too_long(caught, field, max_len):
    """Length is Pydantic's constraint, not the helper's value_error."""
    error = caught.value.errors()[0]
    assert error["loc"] == (field,)
    assert error["type"] == "string_too_long"
    assert error["msg"] == (
        "String should have at most " + str(max_len) + " characters"
    )
    assert error["ctx"]["max_length"] == max_len


_OLD = datetime(2020, 1, 1, tzinfo=timezone.utc)
_NEWER = datetime(2024, 6, 1, tzinfo=timezone.utc)
_CONTROLS = ("\x00", "\x08", "\x0b", "\x0c", "\x1b", "\x7f", "\x85", "\u009f")


def _company(session, ticker, name="Acme"):
    row = CompanyDB(name=name, ticker=ticker)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _pin_updated_at(session, model, row_id, moment):
    stored = session.get(model, row_id)
    stored.updated_at = moment
    session.commit()
    session.refresh(stored)
    return stored.updated_at


class ResearchBehavior:
    """CRUD, scoping, validation, and cascade for notes and theses."""

    def test_limits_and_status_values_match_the_interface(self):
        assert NOTE_BODY_MAX == 10000
        assert THESIS_TITLE_MAX == 200
        assert THESIS_BODY_MAX == 10000
        assert THESIS_BREAKERS_MAX == 5000
        assert ThesisStatus.ACTIVE == "active"
        assert ThesisStatus.CLOSED == "closed"
        # StrEnum: str() is the stored value, not "ThesisStatus.ACTIVE".
        assert str(ThesisStatus.ACTIVE) == "active"
        assert str(ThesisStatus.CLOSED) == "closed"
        assert not issubclass(CompanyNotFoundError, ValueError)

    def test_column_lengths_and_check_use_the_constants(self):
        assert NoteDB.__table__.c.body.type.length == NOTE_BODY_MAX
        assert ThesisDB.__table__.c.title.type.length == THESIS_TITLE_MAX
        assert ThesisDB.__table__.c.body.type.length == THESIS_BODY_MAX
        assert (
            ThesisDB.__table__.c.thesis_breakers.type.length
            == THESIS_BREAKERS_MAX
        )
        note_fk = next(iter(NoteDB.__table__.foreign_keys))
        thesis_fk = next(iter(ThesisDB.__table__.foreign_keys))
        assert note_fk.ondelete == "CASCADE"
        assert thesis_fk.ondelete == "CASCADE"
        assert note_fk.column.table.name == "companies"
        checks = [
            item
            for item in ThesisDB.__table__.constraints
            if item.name == "ck_theses_status"
        ]
        assert len(checks) == 1
        sql = str(checks[0].sqltext)
        assert "active" in sql
        assert "closed" in sql

    def test_note_crud_orders_by_edit_then_id(self, session):
        company = _company(session, "ACME")
        repo = NoteRepository(session)
        first = repo.create(company.id, NoteCreate(body="  first  "))
        second = repo.create(company.id, NoteCreate(body="second"))
        third = repo.create(company.id, NoteCreate(body="third"))
        assert first.body == "first"
        assert first.created_at.utcoffset() == timedelta(0)
        assert first.updated_at.utcoffset() == timedelta(0)

        _pin_updated_at(session, NoteDB, first.id, _NEWER)
        _pin_updated_at(session, NoteDB, second.id, _OLD)
        _pin_updated_at(session, NoteDB, third.id, _OLD)

        listed = repo.list_for_company(company.id)
        assert [item.id for item in listed] == [first.id, third.id, second.id]
        assert repo.get(company.id, second.id).body == "second"
        assert repo.list_for_company(999999) == []

        changed = repo.update(
            company.id,
            second.id,
            NoteUpdate(body="  edited \n line  "),
        )
        assert changed.body == "edited \n line"
        assert changed.updated_at > _OLD
        assert repo.get(company.id, second.id).body == "edited \n line"

        assert repo.delete(company.id, second.id) is True
        assert repo.get(company.id, second.id) is None
        assert repo.delete(company.id, second.id) is False

    def test_empty_note_update_does_not_move_updated_at(self, session):
        company = _company(session, "ACME")
        repo = NoteRepository(session)
        note = repo.create(company.id, NoteCreate(body="keep"))
        stored = _pin_updated_at(session, NoteDB, note.id, _OLD)
        assert stored == _OLD
        again = repo.update(company.id, note.id, NoteUpdate())
        assert again.body == "keep"
        assert again.updated_at == _OLD

    def test_same_body_still_counts_as_an_update(self, session):
        company = _company(session, "ACME")
        repo = NoteRepository(session)
        note = repo.create(company.id, NoteCreate(body="keep"))
        created_at = note.created_at
        _pin_updated_at(session, NoteDB, note.id, _OLD)
        changed = repo.update(company.id, note.id, NoteUpdate(body="keep"))
        assert changed.body == "keep"
        assert changed.created_at == created_at
        assert changed.updated_at > _OLD

    def test_wrong_company_cannot_read_or_change_a_note(self, session):
        owner = _company(session, "OWN", name="Owner")
        other = _company(session, "OTH", name="Other")
        repo = NoteRepository(session)
        note = repo.create(owner.id, NoteCreate(body="secret"))
        _pin_updated_at(session, NoteDB, note.id, _OLD)

        assert repo.get(other.id, note.id) is None
        assert (
            repo.update(other.id, note.id, NoteUpdate(body="hacked")) is None
        )
        assert repo.delete(other.id, note.id) is False
        assert repo.get(owner.id, note.id).body == "secret"
        assert repo.get(owner.id, note.id).updated_at == _OLD
        assert [item.id for item in repo.list_for_company(other.id)] == []

    def test_missing_company_on_create_is_typed_and_the_session_recovers(
        self, session
    ):
        repo = NoteRepository(session)
        theses = ThesisRepository(session)
        with pytest.raises(CompanyNotFoundError) as note_error:
            repo.create(999999, NoteCreate(body="orphan"))
        assert note_error.value.company_id == 999999
        assert note_error.value.__cause__ is None
        with pytest.raises(CompanyNotFoundError) as thesis_error:
            theses.create(999999, ThesisCreate(title="T", body="B"))
        assert thesis_error.value.company_id == 999999
        assert session.query(NoteDB).count() == 0
        assert session.query(ThesisDB).count() == 0

        company = _company(session, "ACME")
        note = repo.create(company.id, NoteCreate(body="kept"))
        assert note.company_id == company.id

    def test_late_missing_company_drops_the_driver_error(
        self, session, monkeypatch
    ):
        company = _company(session, "ACME")
        calls = {"n": 0}

        def missing(_db, _company_id):
            calls["n"] += 1
            return calls["n"] > 1

        def fail_commit():
            raise IntegrityError("INSERT", {}, Exception("fk"))

        monkeypatch.setattr(
            "app.repositories.research_store.missing_company",
            missing,
        )
        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(CompanyNotFoundError) as caught:
            NoteRepository(session).create(company.id, NoteCreate(body="x"))
        assert caught.value.company_id == company.id
        assert caught.value.__cause__ is None
        assert caught.value.__context__ is None

    def test_unexpected_integrity_error_is_reraised_and_session_recovers(
        self, session, monkeypatch
    ):
        company = _company(session, "ACME")

        def fail_commit():
            raise IntegrityError("INSERT", {}, Exception("check"))

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(IntegrityError):
            NoteRepository(session).create(company.id, NoteCreate(body="x"))
        monkeypatch.undo()
        created = NoteRepository(session).create(
            company.id, NoteCreate(body="after")
        )
        assert created.body == "after"
        assert session.query(NoteDB).count() == 1

    def test_thesis_status_filter_and_set_status(self, session):
        company = _company(session, "ACME")
        other = _company(session, "OTH", name="Other")
        repo = ThesisRepository(session)
        active = repo.create(
            company.id,
            ThesisCreate(title="  Grow  ", body=" drivers "),
        )
        closed = repo.create(
            company.id,
            ThesisCreate(
                title="Old",
                body="done",
                thesis_breakers="  ",
                status=ThesisStatus.CLOSED,
            ),
        )
        assert active.status is ThesisStatus.ACTIVE
        assert active.title == "Grow"
        assert active.body == "drivers"
        assert active.thesis_breakers == ""
        assert closed.thesis_breakers == ""
        assert closed.status is ThesisStatus.CLOSED
        assert active.created_at.utcoffset() == timedelta(0)

        _pin_updated_at(session, ThesisDB, active.id, _OLD)
        _pin_updated_at(session, ThesisDB, closed.id, _NEWER)
        listed = repo.list_for_company(company.id)
        assert [item.id for item in listed] == [closed.id, active.id]
        assert [
            item.id for item in repo.list_for_company(company.id, None)
        ] == [
            closed.id,
            active.id,
        ]
        assert [
            item.id
            for item in repo.list_for_company(company.id, ThesisStatus.ACTIVE)
        ] == [active.id]
        assert [
            item.id for item in repo.list_for_company(company.id, "closed")
        ] == [closed.id]
        with pytest.raises(ValueError):
            repo.list_for_company(company.id, "nope")

        unchanged = repo.set_status(company.id, active.id, ThesisStatus.ACTIVE)
        assert unchanged.updated_at == _OLD
        closed_now = repo.set_status(company.id, active.id, "closed")
        assert closed_now.status is ThesisStatus.CLOSED
        assert closed_now.updated_at > _OLD
        assert (
            repo.set_status(other.id, active.id, ThesisStatus.ACTIVE) is None
        )
        assert repo.get(company.id, active.id).status is ThesisStatus.CLOSED
        assert repo.set_status(company.id, 999999, ThesisStatus.ACTIVE) is None

        edited = repo.update(
            company.id,
            closed.id,
            ThesisUpdate(title="  Newer  ", status=ThesisStatus.ACTIVE),
        )
        assert edited.title == "Newer"
        assert edited.status is ThesisStatus.ACTIVE
        assert edited.body == "done"
        body_only = repo.update(
            company.id,
            closed.id,
            ThesisUpdate(body="  revised  "),
        )
        assert body_only.body == "revised"
        assert body_only.title == "Newer"
        assert body_only.status is ThesisStatus.ACTIVE
        assert (
            repo.update(other.id, closed.id, ThesisUpdate(title="no")) is None
        )
        assert repo.get(company.id, closed.id).title == "Newer"
        assert repo.delete(other.id, closed.id) is False
        assert repo.delete(company.id, closed.id) is True
        assert repo.get(company.id, closed.id) is None

    def test_empty_thesis_update_does_not_move_updated_at(self, session):
        company = _company(session, "ACME")
        repo = ThesisRepository(session)
        thesis = repo.create(company.id, ThesisCreate(title="T", body="B"))
        _pin_updated_at(session, ThesisDB, thesis.id, _OLD)
        again = repo.update(company.id, thesis.id, ThesisUpdate())
        assert again.updated_at == _OLD
        assert again.title == "T"

    def test_deleting_the_company_removes_notes_and_theses(self, session):
        company = _company(session, "ACME")
        other = _company(session, "OTH", name="Other")
        NoteRepository(session).create(company.id, NoteCreate(body="n"))
        NoteRepository(session).create(other.id, NoteCreate(body="keep"))
        ThesisRepository(session).create(
            company.id, ThesisCreate(title="T", body="B")
        )
        assert CompanyRepository(session).delete(company.id) is True
        session.expire_all()
        assert (
            session.query(NoteDB).filter_by(company_id=company.id).count() == 0
        )
        assert session.query(ThesisDB).count() == 0
        assert session.query(NoteDB).count() == 1

    def test_raw_delete_uses_the_foreign_key_cascade(self, session):
        company = _company(session, "ACME")
        NoteRepository(session).create(company.id, NoteCreate(body="n"))
        ThesisRepository(session).create(
            company.id, ThesisCreate(title="T", body="B")
        )
        company_id = company.id
        session.execute(
            text("DELETE FROM companies WHERE id = :company_id"),
            {"company_id": company_id},
        )
        session.commit()
        session.expire_all()
        # A raw DELETE removes the row. ``session.get`` on the expired
        # instance raises ObjectDeletedError, so count the table.
        assert (
            session.query(CompanyDB).filter(CompanyDB.id == company_id).count()
            == 0
        )
        assert session.query(NoteDB).count() == 0
        assert session.query(ThesisDB).count() == 0

    def test_company_delete_still_removes_metrics_and_notes(self, session):
        company = _company(session, "ACME")
        session.add(
            FinancialMetricsDB(
                company_id=company.id,
                period_end=datetime(2024, 12, 31, tzinfo=timezone.utc),
                period_type="annual",
            )
        )
        session.commit()
        NoteRepository(session).create(company.id, NoteCreate(body="n"))
        assert CompanyRepository(session).delete(company.id) is True
        session.expire_all()
        assert session.query(FinancialMetricsDB).count() == 0
        assert session.query(NoteDB).count() == 0

    def test_database_rejects_a_status_outside_the_enum(self, session):
        company = _company(session, "ACME")
        session.add(
            ThesisDB(
                company_id=company.id,
                title="T",
                body="B",
                thesis_breakers="",
                status="draft",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        assert session.query(ThesisDB).count() == 0
        created = ThesisRepository(session).create(
            company.id, ThesisCreate(title="T", body="B")
        )
        assert created.status is ThesisStatus.ACTIVE

    @pytest.mark.parametrize(
        "value",
        ["", " ", "\n", "\t", "\r\n", " \n\t "],
        ids=["empty", "space", "LF", "tab", "CRLF", "space-LF-tab-space"],
    )
    def test_blank_note_body_is_rejected(self, value):
        with pytest.raises(ValidationError) as caught:
            NoteCreate(body=value)
        assert _text_failure(caught, "body").code == "blank"

    @pytest.mark.parametrize(
        ("value", "title_code", "body_code"),
        [
            ("", "blank", "blank"),
            (" ", "blank", "blank"),
            ("\n", "control_char", "blank"),
        ],
        ids=["empty", "space", "LF"],
    )
    def test_blank_title_and_thesis_body_are_rejected(
        self, value, title_code, body_code
    ):
        """A newline in a title is a control. A body strips it first."""
        with pytest.raises(ValidationError) as title_error:
            ThesisCreate(title=value, body="body")
        assert _text_failure(title_error, "title").code == title_code
        with pytest.raises(ValidationError) as body_error:
            ThesisCreate(title="title", body=value)
        assert _text_failure(body_error, "body").code == body_code

    @pytest.mark.parametrize(
        "char",
        _CONTROLS,
        ids=["U+%04X" % ord(char) for char in _CONTROLS],
    )
    def test_multiline_fields_reject_other_controls(self, char):
        with pytest.raises(ValidationError) as note_error:
            NoteCreate(body="a" + char + "b")
        assert _text_failure(note_error, "body").code == "control_char"
        with pytest.raises(ValidationError) as body_error:
            ThesisCreate(title="title", body="a" + char + "b")
        assert _text_failure(body_error, "body").code == "control_char"
        with pytest.raises(ValidationError) as breakers_error:
            ThesisCreate(
                title="title",
                body="body",
                thesis_breakers="a" + char + "b",
            )
        assert (
            _text_failure(breakers_error, "thesis_breakers").code
            == "control_char"
        )

    @pytest.mark.parametrize(
        ("char", "stored"),
        [("\n", "\n"), ("\r", "\n"), ("\t", "\t")],
    )
    def test_multiline_fields_keep_line_breaks(self, char, stored):
        """A line break is kept. CR and CRLF are stored as LF."""
        assert NoteCreate(body="a" + char + "b").body == "a" + stored + "b"
        thesis = ThesisCreate(
            title="title",
            body="a" + char + "b",
            thesis_breakers="c" + char + "d",
        )
        assert thesis.body == "a" + stored + "b"
        assert thesis.thesis_breakers == "c" + stored + "d"

    @pytest.mark.parametrize(
        "char",
        ["\n", "\r", "\t", "\x00", "\x7f"],
        ids=["LF", "CR", "tab", "U+0000", "U+007F"],
    )
    def test_title_rejects_every_control(self, char):
        with pytest.raises(ValidationError) as caught:
            ThesisCreate(title="a" + char + "b", body="body")
        assert _text_failure(caught, "title").code == "control_char"

    def test_strip_happens_before_the_length_and_control_checks(self):
        padded = " " + ("x" * NOTE_BODY_MAX) + "\n"
        assert NoteCreate(body=padded).body == "x" * NOTE_BODY_MAX
        with pytest.raises(ValidationError) as note_length:
            NoteCreate(body="x" * (NOTE_BODY_MAX + 1))
        _assert_string_too_long(note_length, "body", NOTE_BODY_MAX)
        assert NoteCreate(body="x" * NOTE_BODY_MAX).body == "x" * NOTE_BODY_MAX

        thesis = ThesisCreate(
            title=" " + ("t" * THESIS_TITLE_MAX) + " ",
            body="\n" + ("b" * THESIS_BODY_MAX) + "\n",
            thesis_breakers=" " + ("k" * THESIS_BREAKERS_MAX) + " ",
        )
        assert thesis.title == "t" * THESIS_TITLE_MAX
        assert thesis.body == "b" * THESIS_BODY_MAX
        assert thesis.thesis_breakers == "k" * THESIS_BREAKERS_MAX
        with pytest.raises(ValidationError) as title_length:
            ThesisCreate(title="t" * (THESIS_TITLE_MAX + 1), body="b")
        _assert_string_too_long(title_length, "title", THESIS_TITLE_MAX)
        with pytest.raises(ValidationError) as body_length:
            ThesisCreate(title="t", body="b" * (THESIS_BODY_MAX + 1))
        _assert_string_too_long(body_length, "body", THESIS_BODY_MAX)
        with pytest.raises(ValidationError) as breakers_length:
            ThesisCreate(
                title="t",
                body="b",
                thesis_breakers="k" * (THESIS_BREAKERS_MAX + 1),
            )
        _assert_string_too_long(
            breakers_length, "thesis_breakers", THESIS_BREAKERS_MAX
        )
        # A trailing newline on a title is a control on the raw
        # text. strip() must not hide it. A body allows the newline
        # and then strips it.
        with pytest.raises(ValidationError) as title_newline:
            ThesisCreate(title="  hello\n", body="body")
        assert title_newline.value.errors()[0]["loc"] == ("title",)
        assert ThesisCreate(title="t", body="  body\n").body == "body"
        assert (
            ThesisCreate(
                title="t", body="b", thesis_breakers="  \n"
            ).thesis_breakers
            == ""
        )

    @pytest.mark.parametrize(
        ("value", "title_code", "body_code"),
        [
            ("\u200b", "blank", "blank"),
            ("\ufeff", "blank", "blank"),
            (" \u200b \ufeff ", "blank", "blank"),
            ("\n\u200c\t", "control_char", "blank"),
            ("\u200d", "blank", "blank"),
        ],
        ids=[
            "U+200B",
            "U+FEFF",
            "spaces-and-Cf",
            "LF-U+200C-tab",
            "U+200D",
        ],
    )
    def test_format_characters_alone_count_as_blank(
        self, value, title_code, body_code
    ):
        """Cf plus whitespace is blank. A letter beside Cf is kept.

        ``\\n\\u200c\\t`` is blank on a body: newline and tab are
        allowed, then strip leaves U+200C. The same text is
        ``control_char`` on a title, because a title rejects the
        newline before strip. Checking only ``loc`` would hide that.
        """
        with pytest.raises(ValidationError) as note_error:
            NoteCreate(body=value)
        assert _text_failure(note_error, "body").code == body_code
        with pytest.raises(ValidationError) as title_error:
            ThesisCreate(title=value, body="drivers")
        assert _text_failure(title_error, "title").code == title_code
        with pytest.raises(ValidationError) as body_error:
            ThesisCreate(title="Growth", body=value)
        assert _text_failure(body_error, "body").code == body_code
        assert (
            ThesisCreate(
                title="Growth",
                body="drivers",
                thesis_breakers=value,
            ).thesis_breakers
            == ""
        )
        with pytest.raises(ValidationError) as note_update:
            NoteUpdate(body=value)
        assert _text_failure(note_update, "body").code == body_code
        with pytest.raises(ValidationError) as title_update:
            ThesisUpdate(title=value)
        assert _text_failure(title_update, "title").code == title_code
        with pytest.raises(ValidationError) as body_update:
            ThesisUpdate(body=value)
        assert _text_failure(body_update, "body").code == body_code
        assert ThesisUpdate(thesis_breakers=value).thesis_breakers == ""

        kept = "a\u200bb"
        assert NoteCreate(body=" " + kept + " ").body == kept
        assert ThesisCreate(title=" " + kept + " ", body="b").title == kept

    def test_non_string_text_is_rejected_by_the_field_type(self):
        with pytest.raises(ValidationError):
            NoteCreate(body=123)
        with pytest.raises(ValidationError):
            ThesisCreate(title=123, body="body")
        with pytest.raises(ValidationError):
            NoteUpdate(body=123)

    def test_update_models_are_optional_and_reject_null_and_controls(self):
        assert NoteUpdate().model_dump(exclude_unset=True) == {}
        assert NoteUpdate(body="  hello  ").body == "hello"
        with pytest.raises(ValidationError):
            NoteUpdate(body=None)
        with pytest.raises(ValidationError):
            NoteUpdate(body="  ")
        with pytest.raises(ValidationError):
            NoteUpdate(body="a\x00b")
        with pytest.raises(ValidationError) as note_length:
            NoteUpdate(body="x" * (NOTE_BODY_MAX + 1))
        _assert_string_too_long(note_length, "body", NOTE_BODY_MAX)
        assert NoteUpdate(body="x" * NOTE_BODY_MAX).body == "x" * NOTE_BODY_MAX

        assert ThesisUpdate().model_dump(exclude_unset=True) == {}
        edited = ThesisUpdate(
            title="  T  ",
            thesis_breakers="  ",
            status="active",
        )
        assert edited.title == "T"
        assert edited.thesis_breakers == ""
        assert edited.status is ThesisStatus.ACTIVE
        with pytest.raises(ValidationError):
            ThesisUpdate(title=None)
        with pytest.raises(ValidationError):
            ThesisUpdate(body=None)
        with pytest.raises(ValidationError):
            ThesisUpdate(thesis_breakers=None)
        with pytest.raises(ValidationError):
            ThesisUpdate(status=None)
        with pytest.raises(ValidationError):
            ThesisUpdate(status="ACTIVE")
        with pytest.raises(ValidationError):
            ThesisUpdate(title="a\nb")
        with pytest.raises(ValidationError) as title_length:
            ThesisUpdate(title="t" * (THESIS_TITLE_MAX + 1))
        _assert_string_too_long(title_length, "title", THESIS_TITLE_MAX)
        assert (
            ThesisUpdate(
                thesis_breakers="k" * THESIS_BREAKERS_MAX
            ).thesis_breakers
            == "k" * THESIS_BREAKERS_MAX
        )

    def test_write_models_reject_unknown_fields(self):
        with pytest.raises(ValidationError):
            NoteCreate(body="hello", company_id=1)
        with pytest.raises(ValidationError):
            NoteUpdate(missing="x")
        with pytest.raises(ValidationError):
            ThesisCreate(title="T", body="B", extra=True)
        with pytest.raises(ValidationError):
            ThesisUpdate(nope="x")

    def test_title_keeps_format_characters_and_rejects_bidi(self):
        """A title uses the same text helper as a body.

        Format characters at the edges stay. One between letters
        stays. Bidi controls are rejected on the raw text, on a
        title and on a body. A line separator (U+2028, U+2029) is
        whitespace, not category Cc, so strip() removes one at an
        edge and a middle one is kept.
        """
        assert ThesisCreate(title="\u200bHello\ufeff", body="b").title == (
            "\u200bHello\ufeff"
        )
        assert ThesisCreate(title=" \u200b Hello \u200d ", body="b").title == (
            "\u200b Hello \u200d"
        )
        assert ThesisCreate(title=" a\u200bb ", body="b").title == "a\u200bb"
        # A format character at the edge is kept, so it counts
        # toward the maximum. The old title rule peeled it off first.
        with pytest.raises(ValidationError) as edge_length:
            ThesisCreate(
                title="\u200b" + ("t" * THESIS_TITLE_MAX),
                body="b",
            )
        _assert_string_too_long(edge_length, "title", THESIS_TITLE_MAX)
        assert (
            ThesisUpdate(title="\u200cKept\u200d").title == "\u200cKept\u200d"
        )
        assert NoteCreate(body="\u200bHello\ufeff").body == "\u200bHello\ufeff"
        for mark in (
            "\u202a",
            "\u202e",
            "\u2066",
            "\u2069",
            "\u200e",
            "\u200f",
            "\u061c",
        ):
            with pytest.raises(ValidationError) as caught:
                ThesisCreate(title="Hello" + mark, body="b")
            assert caught.value.errors()[0]["loc"] == ("title",)
            assert mark not in caught.value.errors()[0]["msg"]
            with pytest.raises(ValidationError):
                ThesisUpdate(title=mark + "Hello")
            with pytest.raises(ValidationError) as body_error:
                NoteCreate(body="Hello" + mark)
            assert body_error.value.errors()[0]["loc"] == ("body",)
            with pytest.raises(ValidationError) as breakers_error:
                ThesisCreate(
                    title="T",
                    body="b",
                    thesis_breakers="Hello" + mark,
                )
            assert breakers_error.value.errors()[0]["loc"] == (
                "thesis_breakers",
            )
        # U+2028 at the edge is whitespace. strip() removes it.
        # One between letters stays, on a title and on a body.
        assert ThesisCreate(title="Hello\u2028", body="b").title == "Hello"
        assert (
            ThesisCreate(title="Hel\u2028lo", body="b").title == "Hel\u2028lo"
        )
        assert NoteCreate(body="Hel\u2028lo").body == "Hel\u2028lo"

    def test_write_models_reject_surrogates_without_echoing_them(self):
        """A lone surrogate is rejected on every write field.

        There is no HTTP route for notes or theses. These models are
        the boundary that route will use. The message does not
        repeat the character.
        """
        raw = "A\ud800B"
        cases = (
            (lambda: NoteCreate(body=raw), ("body",)),
            (lambda: NoteUpdate(body=raw), ("body",)),
            (lambda: ThesisCreate(title=raw, body="b"), ("title",)),
            (lambda: ThesisCreate(title="t", body=raw), ("body",)),
            (
                lambda: ThesisCreate(title="t", body="b", thesis_breakers=raw),
                ("thesis_breakers",),
            ),
            (lambda: ThesisUpdate(title=raw), ("title",)),
            (lambda: ThesisUpdate(body=raw), ("body",)),
            (lambda: ThesisUpdate(thesis_breakers=raw), ("thesis_breakers",)),
        )
        for build, loc in cases:
            with pytest.raises(ValidationError) as caught:
                build()
            error = caught.value.errors()[0]
            assert error["loc"] == loc
            assert "surrogate" in error["msg"]
            assert "\ud800" not in error["msg"]

    def test_multiline_newlines_count_as_one_before_the_length_check(self):
        """CRLF and a lone CR become LF, then the max length applies.

        The strings start and end with a letter so ``strip`` does
        not remove the newlines under test. Exactly the maximum
        passes. One newline more fails.
        """
        exact_note = "a" + ("\r\n" * (NOTE_BODY_MAX - 2)) + "z"
        assert NoteCreate(body=exact_note).body == (
            "a" + ("\n" * (NOTE_BODY_MAX - 2)) + "z"
        )
        assert NoteUpdate(body=exact_note).body == (
            "a" + ("\n" * (NOTE_BODY_MAX - 2)) + "z"
        )
        with pytest.raises(ValidationError):
            NoteCreate(body="a" + ("\r\n" * (NOTE_BODY_MAX - 1)) + "z")
        exact_cr = "a" + ("\r" * (NOTE_BODY_MAX - 2)) + "z"
        assert NoteCreate(body=exact_cr).body == (
            "a" + ("\n" * (NOTE_BODY_MAX - 2)) + "z"
        )
        with pytest.raises(ValidationError):
            NoteCreate(body="a" + ("\r" * (NOTE_BODY_MAX - 1)) + "z")
        assert NoteCreate(body="a\r\nb").body == "a\nb"
        assert NoteCreate(body="a\rb").body == "a\nb"

        exact_body = "a" + ("\r\n" * (THESIS_BODY_MAX - 2)) + "z"
        stored_body = ThesisCreate(title="T", body=exact_body).body
        assert stored_body == "a" + ("\n" * (THESIS_BODY_MAX - 2)) + "z"
        assert len(stored_body) == THESIS_BODY_MAX
        with pytest.raises(ValidationError):
            ThesisCreate(
                title="T",
                body="a" + ("\r\n" * (THESIS_BODY_MAX - 1)) + "z",
            )
        exact_breakers = "a" + ("\r\n" * (THESIS_BREAKERS_MAX - 2)) + "z"
        stored_breakers = ThesisCreate(
            title="T",
            body="B",
            thesis_breakers=exact_breakers,
        ).thesis_breakers
        assert stored_breakers == (
            "a" + ("\n" * (THESIS_BREAKERS_MAX - 2)) + "z"
        )
        assert len(stored_breakers) == THESIS_BREAKERS_MAX
        with pytest.raises(ValidationError):
            ThesisCreate(
                title="T",
                body="B",
                thesis_breakers="a"
                + ("\r\n" * (THESIS_BREAKERS_MAX - 1))
                + "z",
            )
        with pytest.raises(ValidationError):
            ThesisCreate(title="a\rb", body="b")

    def test_timestamps_are_required_and_updates_use_one_utc_clock(
        self, session, monkeypatch
    ):
        """Insert uses the server default. Update uses one UTC clock.

        The columns are NOT NULL and have no ``onupdate``. If the
        database also wrote ``updated_at``, it would not equal this
        frozen instant.
        """
        for column in (
            NoteDB.__table__.c.created_at,
            NoteDB.__table__.c.updated_at,
            ThesisDB.__table__.c.created_at,
            ThesisDB.__table__.c.updated_at,
        ):
            assert column.nullable is False
        assert NoteDB.__table__.c.updated_at.onupdate is None
        assert ThesisDB.__table__.c.updated_at.onupdate is None

        frozen = datetime(2030, 5, 4, 3, 2, 1, tzinfo=timezone.utc)

        class _Clock:
            @staticmethod
            def now(tz=None):
                return frozen

        monkeypatch.setattr(
            "app.repositories.note_repository.datetime",
            _Clock,
        )
        monkeypatch.setattr(
            "app.repositories.thesis_repository.datetime",
            _Clock,
        )
        company = _company(session, "CLOCK")
        notes = NoteRepository(session)
        note = notes.create(company.id, NoteCreate(body="n"))
        assert note.created_at is not None
        assert note.created_at.utcoffset() == timedelta(0)
        assert note.updated_at.utcoffset() == timedelta(0)
        changed = notes.update(company.id, note.id, NoteUpdate(body="n2"))
        assert changed.updated_at == frozen
        assert changed.created_at != frozen

        theses = ThesisRepository(session)
        thesis = theses.create(company.id, ThesisCreate(title="T", body="B"))
        closed = theses.set_status(
            company.id,
            thesis.id,
            ThesisStatus.CLOSED,
        )
        assert closed.updated_at == frozen
        assert closed.created_at != frozen
        edited = theses.update(
            company.id,
            thesis.id,
            ThesisUpdate(title="T2"),
        )
        assert edited.updated_at == frozen

    def test_failed_change_rolls_back_without_driver_text(
        self, session, monkeypatch
    ):
        """Update, delete, and set_status share one rollback path.

        ``commit`` raises a driver error. The repositories roll the
        session back and raise ``ResearchStorageError`` after the
        handler, so ``__cause__`` and ``__context__`` are empty. The
        stored rows are unchanged and the session can read them.
        """
        company = _company(session, "STORE")
        notes = NoteRepository(session)
        theses = ThesisRepository(session)
        note = notes.create(company.id, NoteCreate(body="kept"))
        thesis = theses.create(company.id, ThesisCreate(title="T", body="B"))

        def fail_commit():
            raise OperationalError("UPDATE", {}, Exception("disk"))

        monkeypatch.setattr(session, "commit", fail_commit)

        def assert_storage(call):
            with pytest.raises(ResearchStorageError) as caught:
                call()
            assert str(caught.value) == "Note or thesis could not be stored"
            assert isinstance(caught.value, RuntimeError)
            assert "disk" not in str(caught.value)
            assert caught.value.__cause__ is None
            assert caught.value.__context__ is None

        assert_storage(
            lambda: notes.update(
                company.id,
                note.id,
                NoteUpdate(body="changed"),
            )
        )
        assert_storage(lambda: notes.delete(company.id, note.id))
        assert_storage(
            lambda: theses.update(
                company.id,
                thesis.id,
                ThesisUpdate(body="changed"),
            )
        )
        assert_storage(
            lambda: theses.set_status(
                company.id,
                thesis.id,
                ThesisStatus.CLOSED,
            )
        )
        assert_storage(lambda: theses.delete(company.id, thesis.id))

        monkeypatch.undo()
        assert notes.get(company.id, note.id).body == "kept"
        loaded = theses.get(company.id, thesis.id)
        assert loaded.body == "B"
        assert loaded.status is ThesisStatus.ACTIVE

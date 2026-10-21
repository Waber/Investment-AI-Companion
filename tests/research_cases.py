"""Behaviour of notes and theses, shared by SQLite and PostgreSQL.

The test modules supply a ``session`` fixture. These methods do not
open a database of their own, except through that fixture.
"""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

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
from app.repositories.thesis_repository import ThesisRepository

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

    @pytest.mark.parametrize("value", ["", " ", "\n", "\t", "\r\n", " \n\t "])
    def test_blank_note_body_is_rejected(self, value):
        with pytest.raises(ValidationError) as caught:
            NoteCreate(body=value)
        assert caught.value.errors()[0]["loc"] == ("body",)

    @pytest.mark.parametrize("value", ["", " ", "\n"])
    def test_blank_title_and_thesis_body_are_rejected(self, value):
        with pytest.raises(ValidationError):
            ThesisCreate(title=value, body="body")
        with pytest.raises(ValidationError):
            ThesisCreate(title="title", body=value)

    @pytest.mark.parametrize("char", _CONTROLS)
    def test_multiline_fields_reject_other_controls(self, char):
        with pytest.raises(ValidationError):
            NoteCreate(body="a" + char + "b")
        with pytest.raises(ValidationError):
            ThesisCreate(title="title", body="a" + char + "b")
        with pytest.raises(ValidationError):
            ThesisCreate(
                title="title",
                body="body",
                thesis_breakers="a" + char + "b",
            )

    @pytest.mark.parametrize("char", ["\n", "\r", "\t"])
    def test_multiline_fields_keep_line_breaks(self, char):
        assert NoteCreate(body="a" + char + "b").body == "a" + char + "b"
        thesis = ThesisCreate(
            title="title",
            body="a" + char + "b",
            thesis_breakers="c" + char + "d",
        )
        assert thesis.body == "a" + char + "b"
        assert thesis.thesis_breakers == "c" + char + "d"

    @pytest.mark.parametrize("char", ["\n", "\r", "\t", "\x00", "\x7f"])
    def test_title_rejects_every_control(self, char):
        with pytest.raises(ValidationError) as caught:
            ThesisCreate(title="a" + char + "b", body="body")
        assert caught.value.errors()[0]["loc"] == ("title",)

    def test_strip_happens_before_the_length_and_control_checks(self):
        padded = " " + ("x" * NOTE_BODY_MAX) + "\n"
        assert NoteCreate(body=padded).body == "x" * NOTE_BODY_MAX
        with pytest.raises(ValidationError):
            NoteCreate(body="x" * (NOTE_BODY_MAX + 1))
        assert NoteCreate(body="x" * NOTE_BODY_MAX).body == "x" * NOTE_BODY_MAX

        thesis = ThesisCreate(
            title=" " + ("t" * THESIS_TITLE_MAX) + " ",
            body="\n" + ("b" * THESIS_BODY_MAX) + "\n",
            thesis_breakers=" " + ("k" * THESIS_BREAKERS_MAX) + " ",
        )
        assert thesis.title == "t" * THESIS_TITLE_MAX
        assert thesis.body == "b" * THESIS_BODY_MAX
        assert thesis.thesis_breakers == "k" * THESIS_BREAKERS_MAX
        with pytest.raises(ValidationError):
            ThesisCreate(title="t" * (THESIS_TITLE_MAX + 1), body="b")
        with pytest.raises(ValidationError):
            ThesisCreate(title="t", body="b" * (THESIS_BODY_MAX + 1))
        with pytest.raises(ValidationError):
            ThesisCreate(
                title="t",
                body="b",
                thesis_breakers="k" * (THESIS_BREAKERS_MAX + 1),
            )
        # A trailing newline is whitespace, so strip removes it.
        # A newline between letters is a control character in a title.
        assert ThesisCreate(title="  hello\n", body=" body\n").title == "hello"
        assert ThesisCreate(title="t", body="  body\n").body == "body"
        assert (
            ThesisCreate(
                title="t", body="b", thesis_breakers="  \n"
            ).thesis_breakers
            == ""
        )

    @pytest.mark.parametrize(
        "value",
        ["\u200b", "\ufeff", " \u200b \ufeff ", "\n\u200c\t", "\u200d"],
    )
    def test_format_characters_alone_count_as_blank(self, value):
        """Cf plus whitespace is blank. A letter beside Cf is kept."""
        with pytest.raises(ValidationError) as note_error:
            NoteCreate(body=value)
        assert note_error.value.errors()[0]["loc"] == ("body",)
        with pytest.raises(ValidationError) as title_error:
            ThesisCreate(title=value, body="drivers")
        assert title_error.value.errors()[0]["loc"] == ("title",)
        with pytest.raises(ValidationError) as body_error:
            ThesisCreate(title="Growth", body=value)
        assert body_error.value.errors()[0]["loc"] == ("body",)
        assert (
            ThesisCreate(
                title="Growth",
                body="drivers",
                thesis_breakers=value,
            ).thesis_breakers
            == ""
        )
        with pytest.raises(ValidationError):
            NoteUpdate(body=value)
        with pytest.raises(ValidationError):
            ThesisUpdate(title=value)
        with pytest.raises(ValidationError):
            ThesisUpdate(body=value)
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
        with pytest.raises(ValidationError):
            NoteUpdate(body="x" * (NOTE_BODY_MAX + 1))
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
        with pytest.raises(ValidationError):
            ThesisUpdate(title="t" * (THESIS_TITLE_MAX + 1))
        assert (
            ThesisUpdate(
                thesis_breakers="k" * THESIS_BREAKERS_MAX
            ).thesis_breakers
            == "k" * THESIS_BREAKERS_MAX
        )

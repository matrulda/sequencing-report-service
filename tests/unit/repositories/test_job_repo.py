

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

import pytest

from nextflow_runner_service.models.db_models import SQLAlchemyBase, State
from nextflow_runner_service.repositiories.job_repo import JobRepository


class TestJobRepo(object):

    @pytest.fixture
    def db_session_factory(self):
        engine = create_engine('sqlite:///:memory:', echo=False)
        SQLAlchemyBase.metadata.create_all(engine)

        # Throw some data into the in-memory db
        session_factory = scoped_session(sessionmaker())
        session_factory.configure(bind=engine)
        return session_factory

    def test_add_job(self, db_session_factory):
        with JobRepository(db_session_factory) as repo:
            job = repo.add_job(command_with_env={'command': ['foo'], 'environment': {}})
            assert job.command == ['foo']
            assert job.state == State.PENDING

    def test_get_jobs(self, db_session_factory):
        with JobRepository(db_session_factory) as repo:
            repo.add_job(command_with_env={'command': ['foo'], 'environment': {}})
            repo.add_job(command_with_env={'command': ['bar'], 'environment': {}})
            jobs = repo.get_jobs()
            assert len(jobs) == 2
            assert list(map(lambda x: x.command, jobs)) == [['foo'], ['bar']]

    def test_set_state_of_job(self, db_session_factory):
        with JobRepository(db_session_factory) as repo:
            repo.add_job(['foo'])
            repo.set_state_of_job(1, State.CANCELLED)
            assert repo.get_job(1).state == State.CANCELLED

    def test_set_state_of_job(self, db_session_factory):
        with JobRepository(db_session_factory) as repo:
            assert repo.set_state_of_job(1111, State.CANCELLED) is None

    def test_get_one_pending_job(self, db_session_factory):
        with JobRepository(db_session_factory) as repo:
            repo.add_job(command_with_env={'command': ['foo'], 'environment': {}})
            repo.add_job(command_with_env={'command': ['bar'], 'environment': {}})

            repo.set_state_of_job(1, State.CANCELLED)
            job = repo.get_one_pending_job()

            assert job.job_id == 2

            repo.set_state_of_job(2, State.READY)
            job_again = repo.get_one_pending_job()

            assert job_again is None

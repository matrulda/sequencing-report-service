

import asyncio
import mock
import tempfile
import os
import time

import pytest

from nextflow_runner_service.services.local_runner_service import LocalRunnerService
from nextflow_runner_service.models.db_models import Job, State

from tests.test_utils import MockJobRepository


class TestLocalRunnerService(object):
    @pytest.fixture
    def job_repo_factory(self):
        data = []

        def f():
            return MockJobRepository(data)
        return f

    @pytest.fixture
    def nextflow_log_dirs(self):
        return tempfile.mkdtemp()

    @pytest.mark.asyncio
    @mock.patch(
        "nextflow_runner_service.services.local_runner_service.nextflow_command",
        return_value={
            "command": ["nextflow", "run", "socks"],
            "environment": {},
        },
    )
    async def test_start(
            self,
            mock_nextflow_command,
            job_repo_factory,
            nextflow_log_dirs,
            ):
        pipeline = "seqreports"
        runfolder = 'foo_runfolder'
        local_runner_service = LocalRunnerService(
            job_repo_factory,
            "/path/to/config/dir",
            nextflow_log_dirs,
        )

        with mock.patch("subprocess.Popen"):
            job_id = local_runner_service.start(pipeline, runfolder)

        assert isinstance(local_runner_service.get_job(job_id), Job)

    @pytest.mark.asyncio
    @mock.patch(
        "nextflow_runner_service.services.local_runner_service.nextflow_command",
        return_value={
            "command": ["nextflow", "run", "socks"],
            "environment": {},
        },
    )
    async def test_stop(
            self,
            mock_nextflow_command,
            job_repo_factory,
            nextflow_log_dirs
            ):
        pipeline = "seqreports"
        runfolder = 'foo_runfolder'
        local_runner_service = LocalRunnerService(
            job_repo_factory,
            "/path/to/config/dir",
            nextflow_log_dirs,
        )
        with mock.patch("subprocess.Popen"):
            job_id = local_runner_service.start(pipeline, runfolder)
            time.sleep(1)
            stopped_id = local_runner_service.stop(job_id)

        assert local_runner_service.get_job(stopped_id).state == State.CANCELLED
        assert stopped_id == job_id

    @pytest.mark.asyncio
    async def test_start_process(
            self,
            job_repo_factory,
            nextflow_log_dirs
            ):
        local_runner_service = LocalRunnerService(
            job_repo_factory,
            "/path/to/config/dir",
            nextflow_log_dirs,
        )

        command_with_env = {
            "command": ["sleep", "1"],
            "environment": {},
        }

        with local_runner_service._job_repo_factory() as job_repo:
            job = job_repo.add_job(command_with_env=command_with_env)
            job_id = job.job_id
            assert job.state == State.PENDING

            await local_runner_service._start_process(job_id)

            job = job_repo.get_job(job_id)
            assert job.state == State.DONE

    @pytest.mark.asyncio
    async def test_start_process_fail(
            self,
            job_repo_factory,
            nextflow_log_dirs
            ):
        local_runner_service = LocalRunnerService(
            job_repo_factory,
            "/path/to/config/dir",
            nextflow_log_dirs,
        )

        command_with_env = {
            "command": ["fakecommand"],
            "environment": {},
        }

        with local_runner_service._job_repo_factory() as job_repo:
            job = job_repo.add_job(command_with_env=command_with_env)
            job_id = job.job_id
            assert job.state == State.PENDING

            await local_runner_service._start_process(job_id)

            job = job_repo.get_job(job_id)
            assert job.state == State.ERROR

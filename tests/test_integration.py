import json
import codecs
import tempfile
from pathlib import Path
import os
import shutil
import time
import yaml

from arteria.web.app import AppService

from tornado.testing import AsyncHTTPTestCase, gen_test
from tornado.web import Application

from nextflow_runner_service.app import configure_routes
from nextflow_runner_service.models.db_models import State

import importlib.metadata

version = importlib.metadata.version("nextflow-runner-service")


class TestIntegration(AsyncHTTPTestCase):

    db_file_path = None

    @classmethod
    def setUpClass(self):
        super().setUpClass()
        self.db_file_path = Path(tempfile.NamedTemporaryFile().name)
        self.nextflow_log_dirs = tempfile.mkdtemp()
        self.config_dir = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(self):
        super().tearDownClass()
        if self.db_file_path.exists:
            os.remove(self.db_file_path.name)
        if os.path.exists(self.nextflow_log_dirs):
            shutil.rmtree(self.nextflow_log_dirs, ignore_errors=True)
        if os.path.exists(self.config_dir):
            shutil.rmtree(self.config_dir, ignore_errors=True)

    def get_app(self):
        src_path = (Path(__file__) / '..' / '..').resolve()

        app_config = {
            'port': 9999,
            'db_connection_string': f'sqlite:///{self.db_file_path.name}',
            'alembic_ini_path': str(src_path / 'config/alembic.ini'),
            'alembic_log_config_path': str(src_path / 'config/logger.config'),
            'alembic_scripts': str(src_path / 'alembic/'),
            'reports_dir': str(src_path / 'tests/resources/reports'),
            'monitored_directories': [str(src_path / 'tests/resources/')],
            'nextflow_log_dirs': self.nextflow_log_dirs,
            'pipeline_config_dir': f'{self.config_dir}/pipeline_config/',
        }

        pipeline_configs = {
            "seqreports": {
                'main_workflow_path': str(src_path / 'seqreports/main.nf'),
                'environment': {'NXF_TEMP': '/tmp/'},
                'nextflow_parameters': {
                    'config': str(src_path / 'seqreports/nextflow.config'),
                    'profile': 'singularity,dev,test',
                },
                'pipeline_parameters': {
                    'hello': '{runfolder_path}',
                },
            },
            "socks": {
                'main_workflow_path': "socks",
                'environment': {'NXF_TEMP': '/tmp/'},
                "nextflow_parameters": {
                    "revision": "main",
                },
                "pipeline_parameters": {
                    "style": "ascii",
                    "test_pipeline_param": "{test}"
                },
            },
            "socks_samplesheet": {
                'main_workflow_path': "socks",
                'environment': {'NXF_TEMP': '/tmp/'},
                "nextflow_parameters": {
                    "revision": "main",
                },
                "pipeline_parameters": {
                    "input": "{input_samplesheet_path}",
                },
            },
            "demultiplex": {
                'main_workflow_path': str(src_path / 'seqreports/main.nf'),
                'environment': {'NXF_TEMP': '/tmp/'},
                'nextflow_parameters': {
                    'config': str(src_path / 'seqreports/nextflow.config'),
                    'profile': 'singularity,dev,test',
                },
                'pipeline_parameters': {
                    'demultiplexer': "{demultiplexer}"
                },
            },
        }

        with open(Path(self.config_dir) / "app.config", 'w') as app_config_file:
            app_config_file.write(yaml.dump(app_config))

        Path(app_config["pipeline_config_dir"]).mkdir(exist_ok=True)

        for name, config in pipeline_configs.items():
            with open(
                        Path(self.config_dir) / "pipeline_config" / f"{name}.yml",
                        'w'
                    ) as pipeline_config_file:
                pipeline_config_file.write(yaml.dump(config))

        shutil.copyfile(
            src_path / "config" / "pipeline_config" / "schema.json",
            Path(app_config["pipeline_config_dir"]) / "schema.json"
        )
        shutil.copy(src_path / 'config/logger.config', self.config_dir)

        app_svc = AppService.create(
            product_name="test_delivery_service",
            config_root=self.config_dir,
            args=[])

        config = app_svc.config_svc
        app = Application(configure_routes(config))
        return app

    def test_get_version(self):
        response = self.fetch('/api/1.0/version')
        self.assertEqual(response.code, 200)
        self.assertEqual(json.loads(response.body), {'version': version})

    @gen_test(timeout=240)
    def test_start_job(self):
        response = yield self.http_client.fetch(
            self.get_url('/api/1.0/jobs/start/seqreports/foo_runfolder'),
            method='POST', body=json.dumps({}))
        self.assertEqual(response.code, 202)
        status_link = json.loads(response.body).get('link', None)
        self.assertTrue(status_link)
        status_response = yield self.http_client.fetch(status_link)
        self.assertEqual(status_response.code, 200)
        status_response_body = json.loads(status_response.body)
        self.assertTrue(status_response_body.get('job_id'))
        self.assertTrue(status_response_body.get('state'))

        while status_response_body["state"] in [
                State.NONE.value,
                State.PENDING.value,
                State.READY.value,
                State.STARTED.value,
                ]:
            status_response = yield self.http_client.fetch(status_link)
            self.assertEqual(status_response.code, 200)
            status_response_body = json.loads(status_response.body)
            time.sleep(1)

        self.assertEqual(status_response_body["state"], State.DONE.value)

    def test_start_two_jobs(self):
        status_links = []
        for _ in range(2):
            response = self.fetch(
                '/api/1.0/jobs/start/seqreports/foo_runfolder',
                method='POST', body=json.dumps({}))
            self.assertEqual(response.code, 202)
            status_link = json.loads(response.body).get('link', None)
            status_links.append(status_link)

        time.sleep(2)

        job_ids = []
        for link in status_links:
            status_response = self.fetch(link)
            self.assertEqual(status_response.code, 200)
            response_body = json.loads(status_response.body)
            self.assertEqual(response_body["state"], State.STARTED.value)
            job_ids.append(response_body["job_id"])

        for job_id in job_ids:
            self.fetch(
                f'/api/1.0/jobs/stop/{job_id}',
                method='POST', body=json.dumps({}))

    def test_start_job_missing_pipeline(self):
        response = self.fetch(
            self.get_url('/api/1.0/jobs/start/fake_pipeline/foo_runfolder'),
            method='POST', body=json.dumps({}))
        self.assertEqual(response.code, 404)

    def test_start_job_with_extra_args(self):
        body = {
            "ext_args": "--style emoji",
            "config_parameters": {"test": "test1"}
        }
        response = self.fetch(
            self.get_url('/api/1.0/jobs/start/socks/foo_runfolder'),
            method='POST', body=json.dumps(body))
        self.assertEqual(response.code, 202)
        status_link = json.loads(response.body).get('link', None)
        self.assertTrue(status_link)
        status_response = self.fetch(status_link)
        self.assertEqual(status_response.code, 200)
        status_response_body = json.loads(status_response.body)
        self.assertTrue(status_response_body.get('job_id'))
        self.assertTrue(status_response_body.get('state'))

        while status_response_body["state"] in [
                State.NONE.value,
                State.PENDING.value,
                State.READY.value,
                State.STARTED.value,
                ]:
            status_response = self.fetch(status_link)
            self.assertEqual(status_response.code, 200)
            status_response_body = json.loads(status_response.body)
            time.sleep(1)

        self.assertEqual(status_response_body["state"], State.DONE.value)
        self.assertTrue("🧦" in status_response_body["log"])
        self.assertTrue(
            "--test_pipeline_param" in status_response_body["command"]
        )
        test_cmd_index = status_response_body["command"].index("--test_pipeline_param")
        self.assertTrue(
            status_response_body["command"][test_cmd_index + 1] == "test1"
        )


    def test_start_job_with_input_samplesheet(self):
        body = {
            "input_samplesheet_content": "test,test",
        }
        response = self.fetch(
            self.get_url('/api/1.0/jobs/start/socks_samplesheet/foo_runfolder'),
            method='POST', body=json.dumps(body))
        self.assertEqual(response.code, 202)
        status_link = json.loads(response.body).get('link', None)
        self.assertTrue(status_link)
        status_response = self.fetch(status_link)
        self.assertEqual(status_response.code, 200)
        status_response_body = json.loads(status_response.body)
        self.assertTrue(status_response_body.get('job_id'))
        self.assertTrue(status_response_body.get('state'))

        while status_response_body["state"] in [
                State.NONE.value,
                State.PENDING.value,
                State.READY.value,
                State.STARTED.value,
                ]:
            status_response = self.fetch(status_link)
            self.assertEqual(status_response.code, 200)
            status_response_body = json.loads(status_response.body)
            time.sleep(1)

        src_path = (Path(__file__) / '..' / '..').resolve()
        os.remove(src_path / "tests/resources/foo_runfolder/socks_samplesheet_samplesheet.csv")

        self.assertEqual(status_response_body["state"], State.DONE.value)
        self.assertTrue(
            "socks_samplesheet_samplesheet.csv"
            in " ".join(status_response_body["command"])
        )

    def test_start_job_with_demultiplexer(self):
        body = {
            "config_parameters": {"demultiplexer": "bclconvert"}
        }
        response = self.fetch(
            self.get_url('/api/1.0/jobs/start/demultiplex/foo_runfolder'),
            method='POST', body=json.dumps(body))
        self.assertEqual(response.code, 202)
        status_link = json.loads(response.body).get('link', None)
        self.assertTrue(status_link)
        status_response = self.fetch(status_link)
        self.assertEqual(status_response.code, 200)
        status_response_body = json.loads(status_response.body)
        self.assertTrue(status_response_body.get('job_id'))
        self.assertTrue(status_response_body.get('state'))

        while status_response_body["state"] in [
                State.NONE.value,
                State.PENDING.value,
                State.READY.value,
                State.STARTED.value,
                ]:
            status_response = self.fetch(status_link)
            self.assertEqual(status_response.code, 200)
            status_response_body = json.loads(status_response.body)
            time.sleep(1)

        self.assertTrue("--demultiplexer" in status_response_body["command"])
        demultiplexer_cmd_index = status_response_body["command"].index("--demultiplexer")
        self.assertTrue(
            status_response_body["command"][demultiplexer_cmd_index + 1] == "bclconvert"
        )

    def test_stop_job(self):
        # First start the job
        response = self.fetch(
            '/api/1.0/jobs/start/seqreports/foo_runfolder',
            method='POST', body=json.dumps({}))
        self.assertEqual(response.code, 202)
        status_link = json.loads(response.body).get('link', None)
        self.assertTrue(status_link)
        status_response = self.fetch(status_link)
        body_as_dict = json.loads(status_response.body)
        self.assertTrue(body_as_dict.get('job_id'))
        self.assertTrue(body_as_dict.get('state'))

        # Then stop it
        stop_response = self.fetch('/api/1.0/jobs/stop/{}'.format(body_as_dict['job_id']),
                                   method='POST',
                                   body=json.dumps({}))

        self.assertEqual(stop_response.code, 202)

        # And check its status
        status_after_stop_response = self.fetch(json.loads(stop_response.body)['link'])
        self.assertEqual(json.loads(status_after_stop_response.body)['state'], 'cancelled')

    def test_should_return_current_report(self):
        response = self.fetch('/reports/foo_runfolder/current/')
        self.assertEqual(response.code, 200)
        decoded_body = response.body.decode('UTF-8')
        self.assertIn('MultiQC', decoded_body)
        self.assertIn('VERSION2', decoded_body)

    def test_should_return_specific_report(self):
        response = self.fetch('/reports/foo_runfolder/v1/')
        self.assertEqual(response.code, 200)
        decoded_body = response.body.decode('UTF-8')
        self.assertIn('MultiQC', decoded_body)
        self.assertIn('VERSION1', decoded_body)

    def test_should_return_all_reports(self):
        response = self.fetch('/reports/foo_runfolder')
        self.assertEqual(response.code, 200)
        response_dict = json.loads(response.body)
        self.assertTrue(response_dict.get('links'))
        self.assertSetEqual(set(response_dict['links']),
                            set(['http://127.0.0.1:{}/reports/foo_runfolder/v1/'.format(self.get_http_port()),
                                 'http://127.0.0.1:{}/reports/foo_runfolder/current/'.format(self.get_http_port()),
                                 'http://127.0.0.1:{}/reports/foo_runfolder/v2/'.format(self.get_http_port())]))

import datetime
import tempfile
import pathlib
import shutil
import yaml

import pytest
import jsonschema

from nextflow_runner_service.nextflow import *


@pytest.fixture()
def config():
    return {
        'main_workflow_path': 'Molmed/summary-report-development',
        'nextflow_parameters': {
            'config': 'config/nextflow',
            'profile': 'singularity,snpseq',
        },
        'environment': {
            'NXF_TEMP': '/tmp_foo',
            'TEST_RUNFOLDER': '{runfolder_name}',
            'TEST_PATH': '{runfolder_path}',
            'TEST_YEAR': '{current_year}',
        },
        'pipeline_parameters': {
            'hello': '{runfolder_path}',
            'year': '{current_year}',
            'name': '{runfolder_name}',
        }
    }


@pytest.fixture()
def config_dir(config):
    with tempfile.TemporaryDirectory() as pipeline_config_dir:
        with open(
                pathlib.Path(pipeline_config_dir) / "foo_pipeline.yml",
                'w') as config_file:
            config_file.write(yaml.dump(config))
        shutil.copyfile(
            "config/pipeline_config/schema.json",
            pathlib.Path(pipeline_config_dir) / "schema.json"
        )
        yield pipeline_config_dir


@pytest.fixture()
def runfolder():
    with tempfile.TemporaryDirectory() as runfolder:
        yield pathlib.Path(runfolder)


def test_nextflow_command(config_dir, runfolder):
    result = nextflow_command(
        "foo_pipeline",
        str(runfolder),
        config_dir,
        "samplesheet,content",
        ["--params", "foo"],
    )

    assert result['command'] == [
        'nextflow',
        'run', 'Molmed/summary-report-development',
        '-config', 'config/nextflow',
        '-profile', 'singularity,snpseq',
        '--hello', str(runfolder),
        '--name', runfolder.name,
        '--year', str(datetime.datetime.now().year),
        "--params", "foo",
    ]

    assert result['environment'] == {
        'NXF_TEMP': '/tmp_foo',
        'TEST_RUNFOLDER': runfolder.name,
        'TEST_PATH': str(runfolder),
        'TEST_YEAR': str(datetime.datetime.now().year),
    }

    with open(runfolder / "foo_pipeline_samplesheet.csv") as f:
        assert f.read() == "samplesheet,content"


def test_get_config(config_dir, config):
    test_config = get_config(config_dir, "foo_pipeline")
    assert test_config == config


def test_config_validation(config_dir):
    with open(pathlib.Path(config_dir) / "erronous_pipeline.yml", 'w') as f:
        f.write(yaml.dump({'a': 'b'}))
    with pytest.raises(jsonschema.ValidationError):
        get_config(config_dir, "erronous_pipeline")


def test_config_not_found(config_dir):
    with pytest.raises(FileNotFoundError):
        get_config(config_dir, "erronous_pipeline")


def test_build_config_variables(runfolder):
    config_values = build_config_variables(
        "foo_pipeline",
        str(runfolder),
        "runfolder_data,{runfolder_name}",
        {"demultiplexer":"bcl2fastq"}
    )
    assert config_values == {
        "current_year": datetime.datetime.now().year,
        "runfolder_path": str(runfolder),
        "runfolder_name": runfolder.name,
        "input_samplesheet_path": f"{runfolder}/foo_pipeline_samplesheet.csv",
        "demultiplexer": "bcl2fastq",
    }
    with open(config_values["input_samplesheet_path"], 'r') as f:
        assert f.read() == f"runfolder_data,{runfolder.name}"

def test_interpolate_variables(config):
    config_values = {
        "current_year": 2024,
        "runfolder_path": "/path/to/runfolder",
        "runfolder_name": "runfolder",
    }

    exp_config = {
        'main_workflow_path': 'Molmed/summary-report-development',
        'nextflow_parameters': {
            'config': 'config/nextflow',
            'profile': 'singularity,snpseq',
        },
        'environment': {
            'NXF_TEMP': '/tmp_foo',
            'TEST_RUNFOLDER': 'runfolder',
            'TEST_PATH': '/path/to/runfolder',
            'TEST_YEAR': '2024',
        },
        'pipeline_parameters': {
            'hello': '/path/to/runfolder',
            'year': '2024',
            'name': 'runfolder',
        }
    }

    test_config = interpolate_variables(config, config_values)

    assert test_config == exp_config

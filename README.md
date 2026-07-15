Sequencing Report Service
=========================

Service used to start nextflow pipelines with passed config variables

How to configure pipelines
--------------------------
Pipelines are made available to the service by adding a config file in the specified pipeline config dir. Here follows an example:

app.config:

```bash
[...]
monitored_directories:
    - /data/
pipeline_config_dir: /home/user/pipeline_config_dir
```

/home/user/pipeline_config_dir/mypipeline.yml:

```bash
---

main_workflow_path: /home/user/mypipeline/main.nf
environment:
  NXF_TEMP: /tmp/
  NXF_WORK: /tmp/nf_work/
  NXF_ANSI_LOG: "false"
pipeline_parameters:
  input: "{input_samplesheet_path}"
  outdir: "{runfolder_path}"
  my_parameter: "{my_parameter}"
nextflow_parameters:
  config: /home/user/custom_my_pipeline.config
  profile: docker
input_samplesheet_content: |
  id,samplesheet,lane,flowcell
  {runfolder_name},{runfolder_path}/SampleSheet.csv,,{runfolder_path}
```

The service has support for doing variable substitution in the config. The following values have built-in support and the service will use today's date / information from the config / request data to assemble them:

* {runfolder_name}
* {runfolder_path}
* {current_year}
* {input_samplesheet_path}

It is possible to pass other values as well: In this example, ```my_parameter``` could be passed in the request by adding the following element to the request body:

```bash
config_parameters:  {"my_parameter": "my_value"}
```

When all this is in place, a pipeline job can be started by making the following request:

```bash
curl -X POST -w'\n' localhost:9999/api/1.0/jobs/start/mypipeline/foo_runfolder
```

Given these config vales + request, the resulting app config parameters would become:

```bash
main_workflow_path: /home/user/mypipeline/main.nf
environment:
  NXF_TEMP: /tmp/
  NXF_WORK: /tmp/nf_work/
  NXF_ANSI_LOG: "false"
pipeline_parameters:
  input: /data/foo_runfolder/input_samplesheet.csv
  outdir: /data/foo_runfolder
  my_parameter: my_value
nextflow_parameters:
  config: /home/user/custom_my_pipeline.config
  profile: docker
input_samplesheet_content: |
  id,samplesheet,lane,flowcell
  foo_runfolder,/data/foo_runfolder/SampleSheet.csv,,/data/foo_runfolder
```


Installing nextflow-runner-service
----------------
1. Clone the repo and enter it

2. Install the project and it's dependencies
We use [UV](https://docs.astral.sh/uv/) project manager i.e
```bash
uv sync --all-groups --locked   # this will also create a venv that can be ativated by 'source .venv/bin/activate'
```
See more examples of using UV in the 'Local Development' section below

Starting nextflow-runner-service
----------------
After activating the virtual env, the service can be started with the following command:
```bash
nextflow-runner-service --configroot=config --port 8888
```


Local Development
----------------

#### Dependency management with UV

We use [UV](https://docs.astral.sh/uv/) for fast and reliable Python dependency management. To get started:

1. Install UV:
```bash
pip install uv
```

2. Create and activate virtual environment:
```bash
uv venv --python 3.14
source .venv/bin/activate  # On Unix/macOS
```

3. Install dependencies: (Use '--dev' for dev group )
```bash
# Install all project dependencies from the lockfile
uv sync --all-groups --locked   # --locked assert that the uv.lock will remain unchanged.
```
or
```bash
uv pip install  # Install all project dependencies from the pyproject.toml
```

```bash
uv add <'package'>  # Add dependencies to the project and added to the project's pyproject.toml file.
```

```bash
uv remove <'package'>  # Removes dependencies in the project and removes in the project's pyproject.toml file.
```

#### Running tests
Tests can be executed by running:
```bash
pytest tests
```

#### Dependency Locking

We use UV's lockfile functionality to ensure reproducible builds:
NOTE: `uv add` and `uv remove` usually edit both pyproject.toml and uv.lock but
one can run the command below if you delete the lock file to regenerate

1. Generate/update lockfile:
```bash
uv lock
```

nextflow-runner-service project *version* is documented in the ```pyproject.toml``` file and should be updated there to match the releases.

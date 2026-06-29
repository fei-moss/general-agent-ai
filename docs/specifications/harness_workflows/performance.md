# Harness Workflow Performance Spec

Spec ID: `SPEC-HARNESS-WORKFLOW-001`

Workflow Class: `HARNESS-SPEC-FIRST-FEATURE`

| Metric | Target |
| --- | --- |
| Manifest validation latency | `< 1s on this repository` |
| Release gate overhead | `< 2s excluding existing Python, DockerHost, observability, and pytest checks` |
| Manifest size | `< 128KB` |
| Benchmark command | `time scripts/check_harness_workflows.sh` |

Dynamic workflows can intentionally spend more tokens or machine time when the task needs parallelism, adversarial verification, runtime inspection, or repeated loops. The workflow class must declare the expected budget and stop condition before that extra compute is used.

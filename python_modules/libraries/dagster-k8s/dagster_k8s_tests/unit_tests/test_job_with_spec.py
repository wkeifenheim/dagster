from dagster_k8s.job import DagsterK8sJobConfig, construct_dagster_k8s_job

import yaml


def test_construct_job_with_spec():
    job_spec = """
    metadata: {}
    spec:
        template:
            spec:
                containers:
                - name: pi
                  imagePullPolicy: Always

    """
    cfg = DagsterK8sJobConfig(
        job_image="test/foo:latest",
        dagster_home="/dagster/home",
        instance_config_map="test",
        job_spec=yaml.load(job_spec),
    )
    job = construct_dagster_k8s_job(cfg, ["echo", "dagsterz"], "job123")
    print(job)
    job_dict = job.to_dict()
    assert job_dict["spec"]["template"]["spec"]["containers"][0]["image"] == "test/foo:latest"
    assert job_dict["spec"]["template"]["spec"]["containers"][0]["image_pull_policy"] == "Always"
    assert job_dict["spec"]["template"]["spec"]["containers"][0]["args"] == ["echo", "dagsterz"]

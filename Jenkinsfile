// general-agent-ai production deployment
// Jenkins private config: /data/configurations/ai/prod/general-agent-ai/env.yml
// Remote deployment dir: /data/general-agent-ai
// instance 默认值故意不在可选列表内：未显式选择目标机器时直接失败，避免误发。
def APP_NAME = 'general-agent-ai'
def DEPLOY_ENV = 'prod'
def CONFIG_TEMPLATE = '.env.example'
def CONFIG_NAME = '.env'
def CONFIG_ROOT = '/data/configurations/ai'
def APP_ENV_FILE = 'env.yml'
def DEPLOY_ROOT = '/data'
def TARGET_INSTANCES = 'btcfun-backend-server01'
def INSTANCE_DEFAULT = 'xxxyyy'
def COMPOSE_FILE = 'docker-compose-prd.yml'
def HEALTHCHECK_URL = 'http://localhost:8080/healthz'
def READINESS_URL = 'http://localhost:8080/readyz'

pipeline {
    agent {
        label 'master'
    }

    options {
        disableConcurrentBuilds()
        timeout(time: 45, unit: 'MINUTES')
        timestamps()
    }

    environment {
        binary = "${APP_NAME}"
        deploy_env_dir = "${DEPLOY_ENV}"
        config_template = "${CONFIG_TEMPLATE}"
        config_name = "${CONFIG_NAME}"
        config_root = "${CONFIG_ROOT}"
        app_env_file = "${APP_ENV_FILE}"
        deploy_root = "${DEPLOY_ROOT}"
        instance_default = "${INSTANCE_DEFAULT}"
        compose_file = "${COMPOSE_FILE}"
        healthcheck_url = "${HEALTHCHECK_URL}"
        readiness_url = "${READINESS_URL}"
    }

    parameters {
        extendedChoice(
            defaultValue: INSTANCE_DEFAULT,
            description: 'Multiple choices supported. Must explicitly select target instance.',
            multiSelectDelimiter: ',',
            name: 'instance_name',
            quoteValue: false,
            saveJSONParameterToFile: false,
            type: 'PT_MULTI_SELECT',
            value: TARGET_INSTANCES,
            visibleItemCount: 10
        )
    }

    stages {
        stage('Init') {
            steps {
                cleanWs()
                checkout scm
                dir(env.WORKSPACE) {
                    script {
                        env.git_sha = sh(
                            returnStdout: true,
                            script: 'git rev-parse HEAD'
                        ).trim()
                        env.git_short_sha = env.git_sha.take(12)
                    }
                    sh 'python3 --version'
                    echo "Release Git SHA: ${env.git_sha}"
                }
            }
        }

        stage('Validate Contract') {
            steps {
                dir(env.WORKSPACE) {
                    sh 'python3 scripts/check_production_deployment_contract.py'
                }
            }
        }

        stage('Resolve Env') {
            steps {
                script {
                    def instanceList = (params.instance_name ?: '')
                        .split(',')
                        .collect { it.trim() }
                        .findAll { it }

                    if (instanceList.isEmpty()) {
                        error('instance_name is required')
                    }

                    if (instanceList.contains(env.instance_default)) {
                        error("instance_name must be selected explicitly; invalid default: ${env.instance_default}")
                    }

                    env.instance_list = instanceList.join(',')
                    env.app_env = "${env.config_root}/${env.deploy_env_dir}/${env.binary}/${env.app_env_file}"
                    env.release_archive = "${env.binary}-${env.git_short_sha}-${env.BUILD_NUMBER}.tar.gz"

                    echo "Deploy env: ${env.deploy_env_dir}"
                    echo "Deploy instances: ${env.instance_list}"
                    echo "Config source: ${env.app_env}"
                    echo "Release archive: ${env.release_archive}"
                }
            }
        }

        stage('Render Config') {
            steps {
                dir(env.WORKSPACE) {
                    script {
                        def configFileContent = readFile(env.config_template)
                        def variables = readYaml file: env.app_env
                        if (!(variables instanceof Map)) {
                            error("env.yml must contain a YAML mapping: ${env.app_env}")
                        }

                        // Only treat exact KEY=${KEY} values on non-comment lines as placeholders.
                        // The first comment in .env.example contains a literal ${KEY} example.
                        def placeholderKeys = []
                        configFileContent.readLines().each { line ->
                            def trimmed = line.trim()
                            if (trimmed && !trimmed.startsWith('#')) {
                                def separator = trimmed.indexOf('=')
                                if (separator < 1) {
                                    error("Invalid config template line: ${trimmed}")
                                }
                                def value = trimmed.substring(separator + 1)
                                if (value.startsWith('${') && value.endsWith('}') && value.length() > 3) {
                                    placeholderKeys << value.substring(2, value.length() - 1)
                                }
                            }
                        }
                        placeholderKeys = placeholderKeys.unique().sort()

                        def variableKeys = variables.keySet().collect { it.toString() }
                        def missingKeys = placeholderKeys.findAll { !variables.containsKey(it) }
                        if (!missingKeys.isEmpty()) {
                            error("env.yml missing keys: ${missingKeys.join(', ')}")
                        }

                        def unknownKeys = variableKeys.findAll {
                            !placeholderKeys.contains(it)
                        }.sort()
                        if (!unknownKeys.isEmpty()) {
                            error("env.yml contains unknown keys: ${unknownKeys.join(', ')}")
                        }

                        placeholderKeys.each { key ->
                            def rawValue = variables[key]
                            if (rawValue == null) {
                                error("env.yml value must not be null; use an explicit empty string for: ${key}")
                            }
                            def value = rawValue.toString()
                            if (value.contains('\n') || value.contains('\r')) {
                                error("env.yml value must be single-line: ${key}")
                            }
                            configFileContent = configFileContent.replace("\${${key}}", value)
                        }

                        def unresolvedLines = configFileContent.readLines().findAll { line ->
                            def trimmed = line.trim()
                            trimmed && !trimmed.startsWith('#') && trimmed.contains('${')
                        }
                        if (!unresolvedLines.isEmpty()) {
                            error('Rendered .env still contains unresolved placeholders')
                        }

                        writeFile file: env.config_name, text: configFileContent
                        sh "chmod 600 '${env.config_name}'"
                    }
                }
            }
        }

        stage('Package') {
            steps {
                dir(env.WORKSPACE) {
                    sh '''#!/bin/bash
                        set -euo pipefail
                        tar -czf "../${release_archive}" \
                            --exclude=Jenkinsfile \
                            --exclude=.git \
                            --exclude=.venv \
                            --exclude=venv \
                            --exclude=.pytest_cache \
                            --exclude=.mypy_cache \
                            --exclude=.ruff_cache \
                            --exclude=.artifacts \
                            --exclude='**/__pycache__' \
                            --exclude='*.tar.gz' \
                            --warning=no-file-changed \
                            .
                        mv "../${release_archive}" ./
                    '''
                }
            }
        }

        stage('Deploy') {
            steps {
                script {
                    def instanceList = env.instance_list
                        .split(',')
                        .collect { it.trim() }
                        .findAll { it }
                    def deployTimeoutMs = 2400000
                    def deployDir = "${env.deploy_root}/${env.binary}"
                    def composeCommand = "docker compose --env-file ${env.config_name} -f ${env.compose_file}"
                    def preDeployCommand = "mkdir -p ${deployDir}"
                    def deployCommands = [
                        'set -eu',
                        "cd ${deployDir}",
                        "tar -tzf ${env.release_archive} >/dev/null",
                        "find . -mindepth 1 -maxdepth 1 ! -name '${env.release_archive}' -exec rm -rf -- {} +",
                        "tar -xzf ${env.release_archive}",
                        "rm -f ${env.release_archive}",
                        "chmod 600 ${env.config_name}",
                        "test -f ${env.compose_file} && test -f ${env.config_name} && test -f dockerhost/Dockerfile",
                        "${composeCommand} config >/dev/null",
                        "${composeCommand} up -d --build --remove-orphans",
                        "test \"\$(docker inspect -f '{{.State.ExitCode}}' \"\$(${composeCommand} ps -a -q migrate)\")\" = 0",
                        "for service in api worker reaper; do container_id=\$(${composeCommand} ps -q \"\$service\"); test -n \"\$container_id\"; test \"\$(docker inspect -f '{{.State.Running}}' \"\$container_id\")\" = true; done",
                        "healthy=0; for attempt in \$(seq 1 24); do if test \"\$(docker inspect -f '{{.State.Health.Status}}' \"\$(${composeCommand} ps -q api)\")\" = healthy; then healthy=1; break; fi; sleep 5; done; test \"\$healthy\" = 1",
                        "ready=0; for attempt in \$(seq 1 60); do if ${composeCommand} exec -T api curl -fsS ${env.readiness_url} >/dev/null; then ready=1; break; fi; sleep 5; done; test \"\$ready\" = 1",
                        "${composeCommand} exec -T api curl -sS --fail -o /dev/null -w 'HEALTHZ_HTTP=%{http_code}\\n' ${env.healthcheck_url}",
                        "${composeCommand} exec -T api curl -sS --fail -o /dev/null -w 'READYZ_HTTP=%{http_code}\\n' ${env.readiness_url}",
                        "${composeCommand} ps"
                    ]

                    // A newline-delimited POSIX shell script keeps `set -eu` effective for
                    // compound readiness commands that contain their own semicolons.
                    def deployCommand = deployCommands.join('\n')

                    instanceList.each { instance ->
                        echo "Deploy to instance: ${instance}"
                        sshPublisher publishers: [
                            sshPublisherDesc(
                                configName: "${instance}",
                                transfers: [
                                    sshTransfer(
                                        execCommand: preDeployCommand
                                    ),
                                    sshTransfer(
                                        sourceFiles: "${env.release_archive}",
                                        remoteDirectory: "${env.binary}",
                                        cleanRemote: false,
                                        execTimeout: deployTimeoutMs,
                                        execCommand: deployCommand
                                    )
                                ],
                                verbose: true
                            )
                        ]
                    }
                }
            }
        }
    }

    post {
        always {
            cleanWs(deleteDirs: true, notFailBuild: true)
        }
    }
}

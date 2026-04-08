import hudson.model.FreeStyleProject
import hudson.model.ParametersDefinitionProperty
import hudson.model.StringParameterDefinition
import hudson.tasks.ArtifactArchiver
import hudson.tasks.LogRotator
import hudson.tasks.Shell
import jenkins.model.Jenkins

def jenkins = Jenkins.get()
def jobName = "training-github-allure"

FreeStyleProject job = jenkins.getItem(jobName)
if (job == null) {
  job = jenkins.createProject(FreeStyleProject, jobName)
}

job.setDescription(
  "Training job for student automation practice.\\n" +
  "Parameters: GitHub URL + branch + test command.\\n" +
  "Output: allure-results and generated allure-report archived as build artifacts."
)
job.setBuildDiscarder(new LogRotator(-1, 10, -1, -1))
job.setConcurrentBuild(false)

job.removeProperty(ParametersDefinitionProperty)
job.addProperty(
  new ParametersDefinitionProperty(
    new StringParameterDefinition(
      "GITHUB_URL",
      "https://github.com/danilfg/bank-test-platform-tests.git",
      "Public GitHub repository URL with automated tests."
    ),
    new StringParameterDefinition(
      "GITHUB_BRANCH",
      "main",
      "Git branch to clone."
    ),
    new StringParameterDefinition(
      "TEST_COMMAND",
      "pytest -q",
      "Command to execute tests (allure flag is appended automatically)."
    ),
    new StringParameterDefinition(
      "TEST_API_BASE_URL",
      "http://api-gateway:8080",
      "Base URL for API tests inside Jenkins container network."
    )
  )
)

job.getBuildersList().clear()
job.getBuildersList().add(
  new Shell('''#!/bin/bash
set -euo pipefail

REPO_DIR="$WORKSPACE/repo"
rm -rf "$REPO_DIR" "$WORKSPACE/allure-results" "$WORKSPACE/allure-report"

echo "[INFO] Cloning repository: $GITHUB_URL (branch: $GITHUB_BRANCH)"
git clone --depth 1 --branch "$GITHUB_BRANCH" "$GITHUB_URL" "$REPO_DIR"
cd "$REPO_DIR"

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip

if [ -f requirements.txt ]; then
  pip install -r requirements.txt
elif [ -f requerments.txt ]; then
  # Support common typo found in training repositories.
  pip install -r requerments.txt
fi
pip install pytest allure-pytest

: "${TEST_API_BASE_URL:=http://api-gateway:8080}"
export TEST_API_BASE_URL
echo "[INFO] TEST_API_BASE_URL=$TEST_API_BASE_URL"

set +e
eval "${TEST_COMMAND} --alluredir=allure-results"
TEST_EXIT=$?
set -e

ALLURE_VERSION="2.30.0"
ALLURE_HOME="/tmp/allure-${ALLURE_VERSION}"
if [ ! -x "${ALLURE_HOME}/bin/allure" ]; then
  rm -rf "${ALLURE_HOME}" "/tmp/allure-${ALLURE_VERSION}.tgz"
  curl -fsSL "https://github.com/allure-framework/allure2/releases/download/${ALLURE_VERSION}/allure-${ALLURE_VERSION}.tgz" -o "/tmp/allure-${ALLURE_VERSION}.tgz"
  tar -xzf "/tmp/allure-${ALLURE_VERSION}.tgz" -C /tmp
fi

mkdir -p "$WORKSPACE/allure-results" "$WORKSPACE/allure-report"
if [ -d allure-results ]; then
  cp -R allure-results/. "$WORKSPACE/allure-results/" || true
  "${ALLURE_HOME}/bin/allure" generate allure-results -o "$WORKSPACE/allure-report" --clean || true
fi

echo "[INFO] Build completed with test exit code: ${TEST_EXIT}"

JOB_PATH="$(printf '%s' "$JOB_NAME" | sed 's#/#/job/#g')"
ALLURE_REPORT_PATH="/job/${JOB_PATH}/${BUILD_NUMBER}/artifact/allure-report/index.html"
ALLURE_REPORT_URL="${JENKINS_PUBLIC_URL:-http://127.0.0.1:8086}${ALLURE_REPORT_PATH}"
echo "[INFO] Allure report: ${ALLURE_REPORT_URL}"

if [ -n "${JENKINS_ADMIN_ID:-}" ] && [ -n "${JENKINS_ADMIN_PASSWORD:-}" ]; then
  JENKINS_LOCAL_URL="${JENKINS_LOCAL_URL:-http://127.0.0.1:8080}"
  BUILD_DETAILS_URL="${JENKINS_LOCAL_URL}/job/${JOB_PATH}/${BUILD_NUMBER}/"
  COOKIE_FILE="$(mktemp)"
  CRUMB_JSON="$(curl -fsS -c "${COOKIE_FILE}" -u "${JENKINS_ADMIN_ID}:${JENKINS_ADMIN_PASSWORD}" "${JENKINS_LOCAL_URL}/crumbIssuer/api/json" || true)"
  CRUMB_FIELD="$(printf '%s' "${CRUMB_JSON}" | python3 -c 'import json,sys; print((json.load(sys.stdin)).get("crumbRequestField",""))' 2>/dev/null || true)"
  CRUMB_VALUE="$(printf '%s' "${CRUMB_JSON}" | python3 -c 'import json,sys; print((json.load(sys.stdin)).get("crumb",""))' 2>/dev/null || true)"
  if [ -n "${CRUMB_FIELD}" ] && [ -n "${CRUMB_VALUE}" ]; then
    curl -fsS -b "${COOKIE_FILE}" -u "${JENKINS_ADMIN_ID}:${JENKINS_ADMIN_PASSWORD}" \
      -H "${CRUMB_FIELD}: ${CRUMB_VALUE}" \
      --data-urlencode "description=Allure report: ${ALLURE_REPORT_URL}" \
      "${BUILD_DETAILS_URL}submitDescription" >/dev/null || true
  fi
  rm -f "${COOKIE_FILE}"
fi

exit "${TEST_EXIT}"
''')
)

job.getPublishersList().clear()
def archiver = new ArtifactArchiver("allure-results/**,allure-report/**")
archiver.setAllowEmptyArchive(true)
job.getPublishersList().add(archiver)

job.save()
jenkins.save()

println("Jenkins training job ensured: ${jobName}")

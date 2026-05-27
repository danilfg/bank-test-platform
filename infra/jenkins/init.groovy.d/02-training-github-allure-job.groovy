import hudson.model.ParametersDefinitionProperty
import hudson.model.PasswordParameterDefinition
import hudson.model.StringParameterDefinition
import jenkins.branch.BranchSource
import jenkins.model.Jenkins
import jenkins.plugins.git.GitSCMSource
import org.jenkinsci.plugins.workflow.multibranch.WorkflowBranchProjectFactory
import org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject
import java.util.concurrent.TimeUnit

def jenkins = Jenkins.get()
def jobName = System.getenv("JENKINS_STARTER_JOB_NAME") ?: "training-github-allure"
def repositoryUrl = System.getenv("JENKINS_DEFAULT_REPOSITORY_URL") ?: "https://github.com/danilfg/easybank-jenkins-example-pipeline.git"
def branchName = System.getenv("JENKINS_DEFAULT_BRANCH") ?: "main"
def demoStudentEmail = System.getenv("DEMO_STUDENT_EMAIL") ?: "student@easyitlab.tech"
def demoStudentPassword = System.getenv("DEMO_STUDENT_PASSWORD") ?: "student123"
def legacyJob = jenkins.getItem(jobName)

if (legacyJob != null && !(legacyJob instanceof WorkflowMultiBranchProject)) {
  legacyJob.delete()
  legacyJob = null
  jenkins.save()
  println("Removed legacy root Jenkins job before creating Multibranch Pipeline: ${jobName}")
}

WorkflowMultiBranchProject project = jenkins.getItem(jobName)
if (project == null) {
  project = jenkins.createProject(WorkflowMultiBranchProject, jobName)
}

project.setDescription("Local Open Source training Multibranch Pipeline. Jenkins reads Jenkinsfile from ${repositoryUrl}.")
project.getSourcesList().clear()
def source = new GitSCMSource(null, repositoryUrl, "", branchName, "", false)
project.getSourcesList().add(new BranchSource(source))
def factory = new WorkflowBranchProjectFactory()
factory.setScriptPath("Jenkinsfile")
project.setProjectFactory(factory)
project.save()

def indexing = project.scheduleBuild2(0)
try {
  indexing?.getFuture()?.get(60, TimeUnit.SECONDS)
} catch (Throwable ignored) {
}

try {
  def branchJob = project.getItem(branchName)
  if (branchJob != null) {
    branchJob.removeProperty(ParametersDefinitionProperty.class)
    branchJob.addProperty(new ParametersDefinitionProperty(
      new StringParameterDefinition("TEST_STUDENT_EMAIL", demoStudentEmail, "Local demo student email from .env"),
      new PasswordParameterDefinition("TEST_STUDENT_PASSWORD", demoStudentPassword, "Local demo student password from .env"),
      new StringParameterDefinition("TEST_BRANCH", branchName, "Git branch is configured on the Multibranch job; this is kept for lesson visibility")
    ))
    branchJob.save()
  }
} catch (Throwable parameterError) {
  println("Cannot preconfigure branch parameters: " + parameterError.getMessage())
}

jenkins.save()
println("Jenkins Multibranch training job ensured: ${jobName} -> ${repositoryUrl} (${branchName})")

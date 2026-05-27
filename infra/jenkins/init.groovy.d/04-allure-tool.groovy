import hudson.tools.InstallSourceProperty
import jenkins.model.Jenkins

try {
  def installationClass = Class.forName("org.allurereport.jenkins.tools.AllureCommandlineInstallation")
  def installerClass = Class.forName("org.allurereport.jenkins.tools.AllureCommandlineDirectInstaller")
  def descriptorClass = Class.forName("org.allurereport.jenkins.tools.AllureCommandlineInstallation\$DescriptorImpl")
  def descriptor = Jenkins.get().getDescriptorByType(descriptorClass)
  def installer = installerClass.getConstructor(String.class).newInstance("2.30.0")
  def source = new InstallSourceProperty([installer])
  def installation = installationClass.getConstructor(String.class, String.class, List.class).newInstance("allure-2.30.0", "", [source])
  def array = java.lang.reflect.Array.newInstance(installationClass, 1)
  java.lang.reflect.Array.set(array, 0, installation)
  descriptor.setInstallations(array)
  descriptor.save()
  println("Configured Allure commandline tool: allure-2.30.0")
} catch (Throwable error) {
  println("Allure commandline tool was not configured: ${error.getMessage()}")
}

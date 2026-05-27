import hudson.security.HudsonPrivateSecurityRealm
import hudson.security.Permission
import jenkins.model.Jenkins

def instance = Jenkins.get()
def adminUser = System.getenv("JENKINS_ADMIN_ID") ?: "admin"
def adminPassword = System.getenv("JENKINS_ADMIN_PASSWORD") ?: "admin"

def realm = instance.getSecurityRealm()
if (!(realm instanceof HudsonPrivateSecurityRealm)) {
  realm = new HudsonPrivateSecurityRealm(false)
  instance.setSecurityRealm(realm)
}

def existingAdmin = realm.getUser(adminUser)
if (existingAdmin != null) {
  def user = hudson.model.User.getById(adminUser, false)
  if (user != null) {
    user.delete()
  }
}
realm.createAccount(adminUser, adminPassword)

try {
  def strategyClass = Class.forName("hudson.security.ProjectMatrixAuthorizationStrategy")
  def strategy = strategyClass.newInstance()
  [Jenkins.ADMINISTER, Jenkins.READ].each { Permission permission ->
    strategy.add(permission, adminUser)
  }
  strategy.add(Jenkins.READ, "authenticated")
  instance.setAuthorizationStrategy(strategy)
} catch (Throwable error) {
  def fallbackClass = Class.forName("hudson.security.FullControlOnceLoggedInAuthorizationStrategy")
  def fallback = fallbackClass.newInstance()
  fallback.setAllowAnonymousRead(false)
  instance.setAuthorizationStrategy(fallback)
}

instance.save()
println("Jenkins security bootstrap completed")

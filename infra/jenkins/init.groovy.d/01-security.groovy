import hudson.security.FullControlOnceLoggedInAuthorizationStrategy
import hudson.security.HudsonPrivateSecurityRealm
import jenkins.model.Jenkins

def instance = Jenkins.get()
def adminUser = System.getenv("JENKINS_ADMIN_ID") ?: "admin"
def adminPassword = System.getenv("JENKINS_ADMIN_PASSWORD") ?: "admin"

def realm = instance.getSecurityRealm()
if (!(realm instanceof HudsonPrivateSecurityRealm)) {
  realm = new HudsonPrivateSecurityRealm(false)
  instance.setSecurityRealm(realm)
}

if (realm.getUser(adminUser) == null) {
  realm.createAccount(adminUser, adminPassword)
}

def strategy = instance.getAuthorizationStrategy()
if (!(strategy instanceof FullControlOnceLoggedInAuthorizationStrategy)) {
  def auth = new FullControlOnceLoggedInAuthorizationStrategy()
  auth.setAllowAnonymousRead(false)
  instance.setAuthorizationStrategy(auth)
}

instance.save()
println("Jenkins bootstrap completed")

import hudson.plugins.locale.PluginImpl
import jenkins.model.Jenkins

def instance = Jenkins.get()
def locale = instance.getDescriptorByType(PluginImpl.class)

if (locale != null) {
  locale.setSystemLocale("en_US")
  locale.setIgnoreAcceptLanguage(true)
  locale.save()
  instance.save()
  println("Jenkins locale configured: en_US (browser language ignored)")
} else {
  println("Locale configuration descriptor is not available; skipping locale configuration")
}

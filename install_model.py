"""One-time download; translation is offline afterward."""
import argostranslate.package
argostranslate.package.update_package_index()
packages = argostranslate.package.get_available_packages()
package = next((p for p in packages if p.from_code == 'en' and p.to_code == 'ar'), None)
if package is None:
    raise SystemExit('No English → Arabic package in current index; install a compatible .argosmodel manually.')
argostranslate.package.install_from_path(package.download())
print('English → Arabic model installed.')

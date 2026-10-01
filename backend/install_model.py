"""One-time download; repeat runs preserve an installed English → Arabic model."""
import argostranslate.package
import argostranslate.translate

languages = argostranslate.translate.get_installed_languages()
english = next((lang for lang in languages if lang.code == 'en'), None)
arabic = next((lang for lang in languages if lang.code == 'ar'), None)
if english and arabic and english.get_translation(arabic):
    print('English → Arabic model already installed.')
else:
    argostranslate.package.update_package_index()
    package = next((p for p in argostranslate.package.get_available_packages() if p.from_code == 'en' and p.to_code == 'ar'), None)
    if package is None:
        raise SystemExit('No English → Arabic package in current index; install a compatible .argosmodel manually.')
    argostranslate.package.install_from_path(package.download())
    print('English → Arabic model installed.')

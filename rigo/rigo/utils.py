
import os
import subprocess

from entropy.const import etpConst
from entropy.core.settings.base import SystemSettings
from entropy.misc import ParallelTask

def build_application_store_url(app, sub_page):
    """
    take rigo.models.application.Application object
    and build up HTTP Entropy Application Store URL
    pointing to exact Application page.
    sub_page is used to load a specific part of the page,
    for example "ugc" can be passed to load URL/ugc page.
    """
    settings = SystemSettings()
    details = app.get_details()
    pkg_id, pkg_repo = details.pkg
    branch = settings['repositories']['branch']
    product = settings['repositories']['product']
    url = "%s/show/%s,%s,%s,%s,%s,%s/%s" % (
        etpConst['packages_website_url'],
        details.pkgname,
        pkg_id,
        pkg_repo,
        etpConst['currentarch'],
        branch,
        product,
        sub_page)
    return url

def build_register_url():
    """
    Build User Account Registration Form URL.
    """
    return os.path.join(etpConst['distro_website_url'], "register")

def open_url(url):
    """
    Open the given URL using xdg-open
    """
    def _open_url(url):
        subprocess.call(["xdg-open", url])

    task = ParallelTask(_open_url, url)
    task.name = "UrlOpen"
    task.daemon = True
    task.start()

from core.providers.infra.template.scan_madara_clone import ScanMadaraClone

class CerisetoonProvider(ScanMadaraClone):
    name = 'Cerise toon'
    icon = 'https://i.imgur.com/ycuyRsy.png'
    icon_hash = 'T3mBA4AkUz9sptRplgCb9VU7iHiQiYc'
    lang = 'pt-Br'
    domain = 'cerise.leitorweb.com'

    def __init__(self):
        self.url = 'https://cerise.leitorweb.com'   
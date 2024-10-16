import os
import sys
import json
import subprocess
from PyQt6 import uic
from clipman import init, get
from tldextract import extract
from GUI_qt.logs import LogWindow
from GUI_qt.version import version
from GUI_qt.websites import WebSiteOpener
from GUI_qt.new_version import NewVersion
from GUI_qt.config import get_config, update_lang
from core.providers.domain.chapter_entity import Chapter
from GUI_qt.git import update_providers, get_last_version
from GUI_qt.load_providers import import_classes_recursively, base_path
from PyQt6.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject, QLocale
from core.config.img_conf import get_config as get_img_config, update_img, update_save
from core.providers.application.use_cases import ProviderMangaUseCase, ProviderGetChaptersUseCase, ProviderGetPagesUseCase, ProviderDownloadUseCase
from PyQt6.QtWidgets import QApplication, QMessageBox, QSpacerItem, QSizePolicy, QApplication, QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QWidget

class WorkerSignals(QObject):
    progress_changed = pyqtSignal(int)

class DownloadRunnable(QRunnable):
    def __init__(self, ch, provider):
        super().__init__()
        self.ch = ch
        self.provider = provider
        self.signals = WorkerSignals()

    def run(self):
        try:
            pages = ProviderGetPagesUseCase(self.provider).execute(self.ch)
            def update_progress_bar(value):
                self.signals.progress_changed.emit(int(value))
            ProviderDownloadUseCase(self.provider).execute(pages=pages, fn=update_progress_bar)
        except Exception as e:
            QMessageBox.critical(None, "Erro", f"Falha no download {str(e)}")

class MangaDownloaderApp:
    def __init__(self):
        self.provider_selected = None
        self.manga_id_selectd = None
        self.chapters = []
        self.all_chapters = []
        self.max_concurrent_downloads = 3
        self.download_status = []

        self.providers = import_classes_recursively()
        self.current_dir = os.path.join(base_path(), 'GUI_qt')
        self.assets = os.path.join(self.current_dir, 'assets')

        self.app = QApplication(sys.argv)
        self.window = uic.loadUi(os.path.join(self.assets, 'main.ui'))
        self.window.show()

        self.window.progress_scroll.hide()
        self.window.logs.clicked.connect(self.open_log_window)
        if os.environ.get('PYNEKOENV') != 'dev':
            self.window.logs.hide()

        self.window.progress.clicked.connect(self.open_progress_window)
        self.window.websites.clicked.connect(self.open_websites)
        self.window.downloadAll.clicked.connect(self.download_all_chapters)
        self.window.link.clicked.connect(self.manga_by_link)
        self.window.invert.clicked.connect(self.invert_chapters)
        self.window.search.textChanged.connect(self.filter_chapters)
        self.window.path.textChanged.connect(self.setPath)
        self.window.config.clicked.connect(self.open_config)
        self.window.open_folder.clicked.connect(self.open_folder)
        self.window.config_back.clicked.connect(self.open_home)
        self.window.langs.currentTextChanged.connect(self.langChanged)
        self.window.format_img.currentTextChanged.connect(self.imgFormatChanged)
        self.log_window = None
        self.websites_window = None

        self.vertical_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(self.max_concurrent_downloads)

        self.langChanged()
        self.imgFormatChanged()
        self.setPath()
    
    def run(self):
        sys.exit(self.app.exec())
    
    def chapter_download_button_clicked(self, ch: Chapter, download_button):
        download_button.setEnabled(False)

        runnable = DownloadRunnable(ch, self.provider_selected)
        self.pool.start(runnable)
        self.download_status.append((ch, self.provider_selected, runnable))
        self._load_progress()
    
    def _add_chapters(self):
        for i in reversed(range(self.window.verticalChapter.count())):
            widget = self.window.verticalChapter.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()
        
        self.window.verticalChapter.removeItem(self.vertical_spacer)
        for chapter in self.chapters:
            chapter_ui = uic.loadUi(os.path.join(self.assets, 'chapter.ui'))
            chapter_ui.numberLabel.setText(str(chapter.number))
            for queue in self.download_status:
                ch, _, _ = queue
                if ch.id == chapter.id:
                    chapter_ui.download.setEnabled(False)
            chapter_ui.download.clicked.connect(lambda _, ch=chapter, download_button=chapter_ui.download: self.chapter_download_button_clicked(ch, download_button))
            config = get_config()
            translations = {}
            with open(os.path.join(self.assets, 'translations.json'), 'r', encoding='utf-8') as file:
                translations = json.load(file)
            chapter_ui.download.setText(translations[config.lang]['download'])
            self.window.verticalChapter.addWidget(chapter_ui)
        self.window.verticalChapter.addItem(self.vertical_spacer)
    
    def filter_chapters(self):
        text = self.window.search.text()
        if(text != ''):
            self.chapters = list(filter(lambda chapter: str(chapter.number).find(text)  != -1, self.all_chapters))
        else:
            self.chapters = self.all_chapters
        self._add_chapters()
    
    def invert_chapters(self):
        self.chapters.reverse()
        self._add_chapters()
    
    def manga_by_link(self):
        link = get()
        extract_info = extract(link)
        if extract_info.subdomain:
            domain = f"{extract_info.subdomain}.{extract_info.domain}.{extract_info.suffix}"
        else:
            domain = f"{extract_info.domain}.{extract_info.suffix}"
        provider_find = False
        for provider in self.providers:
            if provider.domain == domain:
                try:
                    self.window.pages.setCurrentIndex(1)
                    QApplication.processEvents()
                    self.provider_selected = provider
                    provider_find = True
                    manga = ProviderMangaUseCase(provider).execute(link)
                    self.manga_id_selectd = manga.id
                    self.window.setWindowTitle(f'PyNeko | {manga.name} | {provider.name}')
                    chapters = ProviderGetChaptersUseCase(provider).execute(manga.id)
                    self.chapters = chapters
                    self.all_chapters = chapters
                    self._add_chapters()
                    self.window.pages.setCurrentIndex(0)
                except Exception as e:
                    self.window.pages.setCurrentIndex(0)
                    QMessageBox.critical(None, "Erro", str(e))
        if provider_find == False:
            config = get_config()
            translations = {}
            with open(os.path.join(self.assets, 'translations.json'), 'r', encoding='utf-8') as file:
                translations = json.load(file)
            translate = translations[config.lang]
            msg = QMessageBox()
            msg.setWindowTitle(translate['error'])
            msg.setText(f"{translate['404_provider']} <span style='color:red;'>{domain}</span> {translate['404_provider2']}")
            msg.exec()
    
    def download_all_chapters(self):
        if self.manga_id_selectd is not None:
            chapters = ProviderGetChaptersUseCase(self.provider_selected).execute(self.manga_id_selectd)
            for i in range(self.window.verticalChapter.count()):
                chapter_ui = self.window.verticalChapter.itemAt(i).widget()
                if isinstance(chapter_ui, QWidget):
                    for ch in chapters:
                        if str(ch.number) == chapter_ui.numberLabel.text():
                            if chapter_ui.download.isEnabled():
                                chapter_ui.download.setEnabled(False)

                                runnable = DownloadRunnable(ch, self.provider_selected)
                                self.pool.start(runnable)
                                self.download_status.append((ch, self.provider_selected, runnable))
                                self._load_progress()
    
    def _load_progress(self):
        for download in self.download_status:
            ch, provider, runnable = download
            
            groupbox = self.window.findChild(QGroupBox, f'groupboxprovider{provider.name}')
            layout = self.window.findChild(QVBoxLayout, f"layoutprovider{provider.name}")
            if groupbox == None: 
                groupbox = QGroupBox()
                groupbox.setTitle(provider.name)
                groupbox.setObjectName(f'groupboxprovider{provider.name}')
                layout = QVBoxLayout()
                layout.setObjectName(f"layoutprovider{provider.name}")
                groupbox.setLayout(layout)
                self.window.verticalProgress.addWidget(groupbox)
            
            groupbox2 = self.window.findChild(QGroupBox, f'groupboxmedia{ch.name}')
            layout2 = self.window.findChild(QVBoxLayout, f"layoutmedia{ch.name}")
            if groupbox2 == None:
                groupbox2 = QGroupBox()
                groupbox2.setTitle(ch.name)
                groupbox2.setObjectName(f'groupboxmedia{ch.name}')
                layout2 = QVBoxLayout()
                layout2.setObjectName(f"layoutmedia{ch.name}")
                groupbox2.setLayout(layout2)
                layout.addWidget(groupbox2)
            
            layout_item = self.window.findChild(QHBoxLayout, f'chaptermedia{ch.name}{ch.id}{provider.name}')
            if layout_item == None:
                layout_item = QHBoxLayout()
                layout_item.setObjectName(f'chaptermedia{ch.name}{ch.id}{provider.name}')
                widget = QWidget()
                widget.setLayout(layout_item)
                label = QLabel()
                label.setText(str(ch.number))
                layout_item.addWidget(label)
                progress_bar = QProgressBar()
                def update_progress_bar(value):
                    progress_bar.setValue(value)
                runnable.signals.progress_changed.connect(update_progress_bar)
                layout_item.addWidget(progress_bar)
                layout2.addWidget(widget)

        for child in self.window.findChildren(QWidget):
            layout = child.layout()
            if layout and layout.objectName().startswith('layoutmedia'):
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    if isinstance(item, QSpacerItem):
                        layout.removeItem(item)
                layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
    
    def imgFormatChanged(self, img=None):
        if not img:
            data = get_img_config()
            self.window.format_img.setCurrentText(data.img)
        else:
            update_img(img)
    
    def setPath(self):
        path = self.window.path.text()
        if not path:
            data = get_img_config()
            self.window.path.setText(data.save)
        else:
            update_save(path)
    
    def open_folder(self):
        path = get_img_config().save
        if sys.platform.startswith('win'):
            os.startfile(path)
        elif sys.platform.startswith('darwin'):
            subprocess.Popen(['open', path])
        else:
            subprocess.Popen(['xdg-open', path])

    def langChanged(self, lang=None):
        translations = {}
        with open(os.path.join(self.assets, 'translations.json'), 'r', encoding='utf-8') as file:
            translations = json.load(file)

        language = lang
        if not lang:
            config = get_config()
            if not config:
                language = QLocale.system().name()
                update_lang(language)
            else:
                language = config.lang
            if language not in translations:
                language = 'en'
            self.window.langs.setCurrentText(language)
        else:
            update_lang(language)

        translation = translations[language]

        self.window.websites.setText(translation['websites'])
        self.window.link.setText(translation['paste'])
        self.window.downloadAll.setText(translation['download_all'])
        self.window.invert.setText(translation['invert'])
        self.window.search.setText(translation['search_caps'])
        self.window.progress.setText(translation['progress'])
        self.window.label.setText(translation['loading'])
        self.window.config.setText(translation['config'])
        self.window.config_back.setText(translation['back'])
        self.window.language_label.setText(translation['language'])
        self.window.img_format.setText(translation['format'])
        self.window.open_folder.setText(translation['open_folder'])
        self.window.path_label.setText(translation['path_label'])
    
    def open_progress_window(self):
        if self.window.progress_scroll.isHidden():
            self.window.progress_scroll.show()
        else:
            self.window.progress_scroll.hide()

    def open_log_window(self):
        if self.log_window is None:
            self.log_window = LogWindow()      
        self.log_window.show()
    
    def open_config(self):
        self.window.pages.setCurrentIndex(2)
    
    def open_home(self):
        self.window.pages.setCurrentIndex(0)

    def open_websites(self):
        if self.websites_window is None:
            self.websites_window = WebSiteOpener(self.providers)
        
        self.websites_window.show()

if __name__ == "__main__":
    try:
        if os.environ.get('PYNEKOENV') != 'dev':
            update_providers()
            if version != get_last_version():
                app = QApplication(sys.argv)
                window = NewVersion()
                window.show()
                sys.exit(app.exec())
        init()
        app = MangaDownloaderApp()
        app.run()
    except Exception as e:
        config = get_config()
        translations = {}
        with open(os.path.join(os.path.join(os.path.join(base_path(), 'GUI_qt'), 'assets'), 'translations.json'), 'r', encoding='utf-8') as file:
            translations = json.load(file)
        new = QApplication(sys.argv)
        translate = translations[config.lang]
        QMessageBox.critical(None, translate['error'], f"{translate['app_error']} {str(e)}")
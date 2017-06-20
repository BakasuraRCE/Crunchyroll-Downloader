#!/usr/bin/env python3
import os
import queue
import threading
from enum import Enum

import colored

import crunchy2mkv as cy


class LoginType(Enum):
    Normal = 1
    Cookie = 2


class Downloader:
    """Downloader wrapper for Crunchyroll"""

    """Public vars"""

    # Login method
    login_type = LoginType.Cookie
    # Cookie login
    user_agent = None
    cookies = None
    # Normal login(not work atm 10-06-17)
    username = None
    password = None

    # Threads downloading at time
    num_worker_threads = 10

    # User download queue
    download_queue = []

    output_path = os.getcwd()
    temp_path = os.getcwd()

    # Verbose level (0, 1, 2)
    verbose_level = 0

    """Private vars"""

    __threads = []
    __download_queue = queue.Queue()

    def _downloader_worker(self):
        while True:
            download_item = self.__download_queue.get()
            if download_item is None:
                break
            if self.verbose_level > 0:
                print(
                    colored.style.BOLD + colored.fore.WHITE + colored.back.DEEP_PINK_4B +
                    "THREAD -> Start:"
                    + colored.style.RESET +
                    ' '
                    + colored.fore.WHITE + colored.back.BLUE +
                    str(download_item)
                    + colored.style.RESET
                )

            real_downloader = cy.Crunchy2Mkv()
            if self.login_type == LoginType.Normal:
                real_downloader.username = self.username
                real_downloader.password = self.password
            elif self.login_type == LoginType.Cookie:
                real_downloader.cookies_file = self.cookies
                real_downloader.user_agent = self.user_agent
            real_downloader.url = download_item['url']
            real_downloader.default_sub = download_item['default_sub']
            real_downloader.season = download_item['season']
            real_downloader.chapter = download_item['chapter']
            real_downloader.verbose_level = self.verbose_level
            real_downloader.output_path = self.output_path
            real_downloader.temp_path = self.temp_path

            if not real_downloader.download_video():
                if self.verbose_level > 0:
                    print(
                        colored.style.BOLD + colored.fore.WHITE + colored.back.RED +
                        "THREAD -> ERROR:"
                        + colored.style.RESET +
                        ' '
                        + colored.fore.WHITE + colored.back.BLUE +
                        str(download_item)
                        + colored.style.RESET
                    )
            else:
                if self.verbose_level > 0:
                    print(
                        colored.style.BOLD + colored.fore.WHITE + colored.back.GREEN +
                        "THREAD -> END:"
                        + colored.style.RESET +
                        ' '
                        + colored.fore.WHITE + colored.back.BLUE +
                        str(download_item)
                        + colored.style.RESET
                    )
            self.__download_queue.task_done()

    def start(self):
        """Start the downloads"""

        for i in range(self.num_worker_threads):
            t = threading.Thread(target=self._downloader_worker)
            t.daemon = True
            t.start()
            self.__threads.append(t)

        for download in self.download_queue:
            chapter_list = []
            if 'chapter' in download:
                chapter_list.append(download['chapter'])
            elif 'from' in download and 'to' in download:
                for x in range(download['from'], download['to'] + 1):
                    chapter_list.append(x)
            else:
                continue

            for chapter in chapter_list:
                self.__download_queue.put({
                    'url': download['url'],
                    'default_sub': download['default_sub'],
                    'season': download['season'],
                    'chapter': chapter
                })

        # block until all tasks are done
        self.__download_queue.join()

        # stop workers
        for i in range(self.num_worker_threads):
            self.__download_queue.put(None)
        for t in self.__threads:
            t.join()

#!/usr/bin/env python3
import glob
import os
import re
import shutil
import sys
from distutils.spawn import find_executable
from subprocess import check_call, CalledProcessError
from tempfile import mkdtemp

import colored


class Crunchy2Mkv:
    """crunchy2mkv
    Download .flv videos from Crunchyroll (and maybe other sites) and
    convert them to .mkv.

    Needs youtube-dl and mkvmerge (from mkvtoolnix) installed and
    accessible from PATH (or you can change global variables YTDL_PATH and
    MKVMERGE_PATH to point to your installation path).

    No configuration files. You can change the default behavior of this
    script by changing the following global variables:

        RESULT_PATH: default directory for resulting videos
        USERNAME: username from Crunchyroll (or other video services)
        PASSWORD: same for password
        QUALITY: default video quality
        SUBS: comma-separated string including each desired language for
        subtitles. Use "all" to download everything.

    Based on https://pypi.python.org/pypi/crunchy2mkv
    """

    if sys.platform == "win32":
        __YTDL_PATH = "youtube_dl.exe"
        __MKVMERGE_PATH = "mkvmerge.exe"
    else:
        __YTDL_PATH = find_executable("youtube-dl")
        __MKVMERGE_PATH = find_executable("mkvmerge")
    if not __YTDL_PATH:
        sys.exit("Could not find youtube-dl installed.")
    if not __MKVMERGE_PATH:
        sys.exit("Could not find mkvmerge installed.")

    # Target path
    output_path = None
    # Temp download path
    temp_path = None

    # Url
    url = None

    # Cookie login
    cookies_file = None
    user_agent = None
    # Normal login(not work atm 10-06-17)
    username = None
    password = None

    # worst, 360p, 480p, 720p, 1080p, best
    quality = "best"
    # "en"/"en,pt"/""
    subs = "all"
    # default sub
    default_sub = "esLA"
    # season
    season = 1
    # chapter
    chapter = 0

    # Verbose level (0, 1, 2)
    verbose_level = 0

    # language codes
    _SUBS_NAMES = {"frFR": "fre", "itIT": "ita", "esLA": "spa", "enUS": "eng", "esES": "spa", "deDE": "ger", "arME": "ara", "ptBR": "por"}
    # Don't change these settings unless you know what you're doing!
    __SUPPORTED_EXTENSIONS = ["flv", "mp4", "ogg", "webm"]
    __DEVNULL = open(os.devnull, "wb")

    def _youtube_dl(self, download_path):
        """Simple youtube-dl wrapper

        url -- Video url to download
        username (default = None) -- username to be passed to "--username"
        option in youtube-dl
        password (default = None) -- password to be passed to "--password"
        option in youtube-dl
        quality (default = "best") -- quality to be passed to "--quality"
        option in youtube-dl
        subs (default = "all") -- subtitle(s) language to download. If
        "all" is used the, option "--all-subs" is passed to youtube-dl,
        otherwise the passed string is passed to "--subs-lang" option
        in youtube-dl, without any checks. If None is passed, this option
        is ignored.
        verbose -- show youtube-dl output in stdout/stderr
        """
        # Basic command line
        cmd = [self.__YTDL_PATH, "-f", self.quality, "--ignore-config", "--output", download_path + "/%(title)s.%(ext)s"]

        # Add login(by cookies) information
        if self.cookies_file:
            cmd.append("--cookies")
            cmd.append(self.cookies_file)
        if self.user_agent:
            cmd.append("--user-agent")
            cmd.append(self.user_agent)

        # Add login information
        if self.username:
            cmd.append("--username")
            cmd.append(self.username)
        if self.password:
            cmd.append("--password")
            cmd.append(self.password)

        if (int(self.chapter) > 0):
            cmd.append("--playlist-items")
            cmd.append(str(self.chapter))

        # Add subtitle preference
        if self.subs:
            if self.subs == "all":
                cmd.append("--all-subs")
            else:
                cmd.append("--sub-lang")
                cmd.append(self.subs)

        # Add video URL
        cmd.append(self.url)

        # Try to download video
        if self.verbose_level > 0:
            print(
                colored.style.BOLD + colored.fore.WHITE + colored.back.DEEP_PINK_4B +
                "Trying to download video from URL:"
                + colored.style.RESET +
                ' '
                + colored.fore.WHITE + colored.back.BLUE +
                self.url
                + colored.style.RESET
            )
            print(
                colored.style.BOLD + colored.fore.WHITE + colored.back.DEEP_PINK_4B +
                "Running command:"
                + colored.style.RESET +
                ' '
                + colored.fore.WHITE + colored.back.BLUE +
                ' '.join(cmd)
                + colored.style.RESET
            )
        try:
            if self.verbose_level > 1:
                check_call(cmd)
            else:
                check_call(cmd, stderr=self.__DEVNULL, stdout=self.__DEVNULL)
        except CalledProcessError:
            if self.verbose_level > 0:
                print(
                    colored.style.BOLD + colored.fore.WHITE + colored.back.RED +
                    "Error while downloading URL {}.".format(self.url)
                    + colored.style.RESET
                )
            return False

        return True

    def _video2mkv(self, file_path):
        """Simple mkvmerge wrapper to convert videos to .mkv

        file_path -- target video to be converted to .mkv
        result_path -- directory for resulting files in .mkv
        verbose -- show mkvmerge output in stdout/stderr
        """
        # Basic command line
        cmd = [self.__MKVMERGE_PATH]

        # Split filename and extension
        filename, extension = os.path.splitext(file_path)

        # Added output file
        result_filename = os.path.join(self.output_path, os.path.basename(filename))
        result_filename = re.sub(r"(.+) Episodio (\d{1,3})(?: [–-] )*(.+)", lambda m: (
            m.group(1) + " - S" + "%02d" % (int(self.season),) + "E" + "%02d" % (int(m.group(2)),) + " - " + m.group(3)),
                                 result_filename, flags=re.IGNORECASE)
        cmd.append("--output")
        cmd.append("{}.mkv".format(result_filename))

        # add video file and define language
        cmd.append("--language")
        cmd.append("0:jpn")
        cmd.append("--language")
        cmd.append("1:jpn")
        cmd.append(file_path)

        # add all subtitles
        for media in sorted(glob.glob("{}.*".format(filename))):
            filename_parts = media.rsplit(".", 2)
            if (len(filename_parts) == 3) and ((filename_parts[2] == "ass") or (filename_parts[2] == "srt")):
                if any(filename_parts[1] in code for code in self._SUBS_NAMES):
                    cmd.append("--language")
                    cmd.append("0:" + self._SUBS_NAMES[filename_parts[1]])
                else:
                    cmd.append("--language")
                    cmd.append("0:und")
                cmd.append("--track-name")
                cmd.append("0:" + filename_parts[1])
                # define as default sun
                if (filename_parts[1] == self.default_sub):
                    cmd.append("--default-track")
                    cmd.append("0:yes")
                cmd.append(media)

        if self.verbose_level > 0:
            # Try to create .mkv file
            print(
                colored.style.BOLD + colored.fore.WHITE + colored.back.DEEP_PINK_4B +
                'Trying to create'
                + colored.style.RESET +
                ' '
                + colored.fore.WHITE + colored.back.BLUE +
                '{}.mkv.'.format(result_filename)
                + colored.style.RESET
            )
            print(
                colored.style.BOLD + colored.fore.WHITE + colored.back.DEEP_PINK_4B +
                "Running command:"
                + colored.style.RESET +
                ' '
                + colored.fore.WHITE + colored.back.BLUE +
                ' '.join(cmd)
                + colored.style.RESET
            )

        try:
            if self.verbose_level > 1:
                check_call(cmd)
            else:
                check_call(cmd, stderr=self.__DEVNULL, stdout=self.__DEVNULL)
        except CalledProcessError:
            if self.verbose_level > 0:
                print(
                    colored.style.BOLD + colored.fore.WHITE + colored.back.RED +
                    'Error while creating {} file.'.format(result_filename)
                    + colored.style.RESET
                )
            return False

        return '{}.mkv'.format(result_filename)

    def _clean_up_directory(self, directory):
        if self.verbose_level > 0:
            print(
                colored.style.BOLD + colored.fore.WHITE + colored.back.DEEP_PINK_4B +
                'Cleaning up directory:'
                + colored.style.RESET +
                ' '
                + colored.fore.WHITE + colored.back.BLUE +
                '{}'.format(directory)
                + colored.style.RESET
            )
        directory = os.path.abspath(directory)
        shutil.rmtree(directory)

    def download_video(self):
        # Create temp dir
        temp_dir = mkdtemp(dir=self.temp_path)
        # Target path
        self.output_path = os.path.abspath(self.output_path)

        try:
            # Download video
            if not self._youtube_dl(temp_dir):
                return False

            # Convert to MKV
            for file_ext in self.__SUPPORTED_EXTENSIONS:
                filename = sorted(glob.glob(temp_dir + "/*.{}".format(file_ext)))
                if filename:
                    filename = filename[0]
                    result_filename = self._video2mkv(filename)
                    if result_filename == False:
                        return False
                    if self.verbose_level > 0:
                        print(
                            colored.style.BOLD + colored.fore.WHITE + colored.back.GREEN +
                            'Video {} Download successfully!'.format(result_filename)
                            + colored.style.RESET
                        )
        finally:
            self._clean_up_directory(temp_dir)
        return True

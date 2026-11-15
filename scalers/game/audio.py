"""background music: a file dropped into assets/music/, or a direct link to an audio file.

for each scene (menu / shop / battle) these are tried best-first, and a source that fails
(corrupt file, unsupported format, dead link) is skipped in favour of the next one:
  1. assets/music/<scene>.mp3 (or .ogg / .wav)
  2. config.BGM[<scene>]: a file name inside assets/music, or a direct http(s) link
  3. assets/music/bgm.mp3 (or .ogg / .wav)
  4. config.BGM["default"]
links are downloaded once, on a background thread so the game never freezes, and cached in
assets/music/cache/. a link has to point straight at an audio file (YouTube/Spotify pages won't work)
"""
import glob
import hashlib
import os
import threading
import urllib.request
from urllib.parse import urlparse

import pygame

from . import config

AUDIO_EXTS = (".mp3", ".ogg", ".wav")
CONTENT_TYPES = {
    "audio/mpeg": ".mp3", "audio/mp3": ".mp3",
    "audio/ogg": ".ogg", "application/ogg": ".ogg",
    "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/wave": ".wav", "audio/vnd.wave": ".wav",
}
MAX_BYTES = 50 * 1024 * 1024


def _dropins(name):
    """every assets/music/<name>.<ext> that exists, in AUDIO_EXTS order"""
    paths = (os.path.join(config.MUSIC_DIR, name + ext) for ext in AUDIO_EXTS)
    return [p for p in paths if os.path.exists(p)]


def _from_setting(value):
    if not value:
        return None
    if value.lower().startswith(("http://", "https://")):
        return ("url", value)
    path = value if os.path.isabs(value) else os.path.join(config.MUSIC_DIR, value)
    return ("file", path) if os.path.exists(path) else None


# scenes whose own music slot falls back to another scene's slot before the shared bgm / default
FALLBACK = {"gacha": "menu", "create_pack": "menu"}


def candidates(key):
    """every source that could play on this scene, best first: ("file", path) or ("url", link)"""
    found = [("file", p) for p in _dropins(key)]
    found.append(_from_setting(config.BGM.get(key)))
    parent = FALLBACK.get(key)
    if parent:
        found += [("file", p) for p in _dropins(parent)]
        found.append(_from_setting(config.BGM.get(parent)))
    found += [("file", p) for p in _dropins("bgm")]
    found.append(_from_setting(config.BGM.get("default")))
    out = []
    for source in found:
        if source and source not in out:
            out.append(source)
    return out


def resolve(key):
    """the best source for a scene, or None"""
    found = candidates(key)
    return found[0] if found else None


def _cache_dir():
    return os.path.join(config.MUSIC_DIR, "cache")


def _url_hash(url):
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def explain(path, error):
    """a plain-English message for a file the mixer refused to play"""
    name = os.path.basename(path)
    text = str(error)
    if "vorbis" in text.lower() or "ogg" in text.lower():
        why = ("it is an Ogg file but not Ogg Vorbis (very often Ogg Opus, or a renamed video/other format). "
               "Re-export it as .mp3 or as Ogg Vorbis")
    else:
        why = "the file may be corrupt or in an unsupported format. Try re-exporting it as .mp3"
    return f"[music] can't play {name}: {why}. ({text})"


class MusicPlayer:
    def __init__(self):
        self.ok = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.set_volume(config.BGM_VOLUME)
            self.ok = True
        except pygame.error as e:  # no audio device: the game just runs silent
            print(f"[music] audio unavailable: {e}")
        self.key = None
        self.sources = []
        self.playing = None  # file path currently playing
        self._waiting = None  # link we are waiting on (still downloading)
        self._links = {}  # url -> "pending" | "failed" | local path
        self._bad = set()  # files pygame could not play
        self._lock = threading.Lock()

    # public -
    def set_scene(self, key):
        if key == self.key:
            return
        self.key = key
        self.sources = candidates(key)
        self._apply()

    def update(self):
        """call every frame: moves on once a link finishes downloading (or fails)"""
        if self._waiting:
            with self._lock:
                state = self._links.get(self._waiting)
            if state != "pending":
                self._apply()

    def stop(self):
        if self.ok:
            pygame.mixer.music.stop()
        self.playing = None

    # internals -
    def _apply(self):
        """play the best source that works; skip ones that failed, wait on one still downloading"""
        if not self.ok:
            return
        self._waiting = None
        for kind, value in self.sources:
            if kind == "file":
                path = value
            else:
                path = self._link_path(value)
                if path is None:
                    with self._lock:
                        state = self._links.get(value)
                    if state == "pending":
                        self._waiting = value
                        self.stop()
                        return
                    if state == "failed":
                        continue  # the link failed: try the next source
                    path = state  # the download finished in the meantime: play it
            if path in self._bad:
                continue
            if path == self.playing:  # same track as the previous scene keeps playing
                return
            if self._play(path):
                return
        self.stop()

    def _play(self, path):
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(-1, fade_ms=400)
        except pygame.error as e:
            print(explain(path, e))
            self._bad.add(path)
            return False
        self.playing = path
        return True

    def _link_path(self, url):
        """local file for a link, or None while it downloads / if it failed"""
        with self._lock:
            state = self._links.get(url)
            if state == "pending" or state == "failed":
                return None
            if state:
                return state
            cached = glob.glob(os.path.join(_cache_dir(), _url_hash(url) + ".*"))
            if cached:
                self._links[url] = cached[0]
                return cached[0]
            self._links[url] = "pending"
        threading.Thread(target=self._download, args=(url,), daemon=True).start()
        return None

    def _download(self, url):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (game music fetch)"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                ext = os.path.splitext(urlparse(url).path.lower())[1]
                if ext not in AUDIO_EXTS:
                    ext = CONTENT_TYPES.get(resp.headers.get_content_type())
                if ext is None:
                    raise ValueError(f"not a direct audio link (got {resp.headers.get_content_type()})")
                data = resp.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError("file is bigger than 50 MB")
            os.makedirs(_cache_dir(), exist_ok=True)
            path = os.path.join(_cache_dir(), _url_hash(url) + ext)
            with open(path + ".part", "wb") as f:
                f.write(data)
            os.replace(path + ".part", path)
            result = path
        except Exception as e:
            print(f"[music] could not fetch {url}: {e}")
            result = "failed"
        with self._lock:
            self._links[url] = result

Background music. Two ways to set it up, per screen: menu, shop, battle.

1. DROP A FILE here, named after the screen:  menu.mp3  shop.mp3  battle.mp3
   (.ogg and .wav work too). Name one bgm.mp3 to use it for every screen that has no file of its own.

2. USE A LINK: open game/config.py and set BGM, e.g.
       BGM = {"default": "https://example.com/song.mp3", "menu": None, "shop": None, "battle": None}
   A value can also be a file name inside this folder, e.g. "my_song.mp3".

The link must point straight at an audio file (.mp3/.ogg/.wav). YouTube, Spotify or SoundCloud page
links will NOT work. Links download once into assets/music/cache/ (a download never freezes the game;
the music starts when it finishes), so later runs are instant and work offline.

FORMATS: .mp3 and .wav always work. .ogg only works if it is Ogg VORBIS. An .ogg that is Ogg Opus (common
from yt-dlp, Discord, phone recorders) will NOT play; the game prints a message and uses the next source.
Convert with ffmpeg (https://ffmpeg.org) or export from Audacity:
    ffmpeg -i battle.ogg -codec:a libmp3lame -q:a 2 battle.mp3
    ffmpeg -i battle.ogg -c:a libvorbis -q:a 5 battle_fixed.ogg
(an .mp3 next to a bad .ogg of the same name is picked first)

Order per screen: <screen> file, then BGM[<screen>], then bgm file, then BGM["default"].
A source that fails (bad file, dead link) is skipped and the next one in this order is used.
If the same track is chosen for two screens it keeps playing without restarting.
Volume is BGM_VOLUME in game/config.py.

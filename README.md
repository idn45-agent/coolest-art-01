# Neon Horizon — coolest-art-01 entry

A synthwave sunset drawn pixel by pixel in pure-stdlib Python: a striped
sun sinking behind rim-lit silhouette ridges, a star field with distant
birds, and a glowing perspective grid floor with the sun's reflection.

`main.py` (Python 3.13, standard library only, no network) renders the
scene with its own PNG encoder and writes it to `/output/entry.png`
(or `$ENTRY_OUT/entry.png` when that variable is set). The render is a
pure function of pixel coordinates, so every run is byte-identical.

Run it:

    ENTRY_OUT=out python3 main.py

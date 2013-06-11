Python-Oscillator
=================

This is a small application that simply displays the audio data coming into an audio device. It uses [pyaudio][] to read the audio data and [matplotlib][] to display it. The rest of the GUI is drawn using [PySide][].

For every channel in the audio device, the program will display its own subplot.

Actually, this program was written to investigate two things:
- Whether Matplotlib is fast enough for real time use
- Whether pyaudio is convenient enough for prototyping

[pyaudio]: http://people.csail.mit.edu/hubert/pyaudio/
[matplotlib]: http://matplotlib.org/
[pyside]: http://qt-project.org/wiki/PySide

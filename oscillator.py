import sys
import time
from pyaudio import PyAudio, paFloat32, paContinue
import numpy
from PyQt4 import QtCore, QtGui
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg


"""A simple oscillator that shows the waveform of whatever audio is
playing on a sound card.

This is meant to be a testing tool for sound cards and pyaudio. In
writing this, I realized that pyaudio needs to be updated to something
more pythonic. I am sick of juggling device indices and API indices.

Note that this is using PyQt4. You must set your Matplotlib to use
PyQt4 as well. If you have set your Matplotlib to use PySide instead,
just change the import statement above--no other code changes are
necessary.

"""


# meant for monkey patching into pyaudio
def device_index_to_host_api_device_index(self, device_index, host_api_index):
    count = 0;
    for n in range(device_index):
        device_info = self.get_device_info_by_index(n)
        if device_info["hostApi"] == host_api_index:
            count += 1
    return count


class MainWindow(QtGui.QMainWindow):
    """ A Qt QMainWindow that is home to a matplotlib figure and two combo
    boxes. The combo boxes allow the selection of a sound card by API and
    name. The figure will show the waveform of the audio input of that sound
    card.
    """

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)

        # Monkey patch missing methods into PyAudio.
        PyAudio.device_index_to_host_api_device_index = (
            device_index_to_host_api_device_index)

        self.pyaudio = PyAudio()

        # Create the UI widgets.
        central_widget = QtGui.QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QtGui.QVBoxLayout(central_widget)
        self.figure = FigureWidget()
        main_layout.addWidget(self.figure)
        horizontal_layout = QtGui.QHBoxLayout()
        main_layout.addLayout(horizontal_layout)
        api_list = QtGui.QComboBox()
        api_list.setModel(APIListModel(self.pyaudio))
        horizontal_layout.addWidget(api_list)
        device_list = QtGui.QComboBox()
        device_list_model = DeviceListModel(self.pyaudio)
        device_list.setModel(device_list_model)
        horizontal_layout.addWidget(device_list)

        # Connect the moving parts
        api_list.currentIndexChanged.connect(device_list_model.set_api_index)
        api_list.currentIndexChanged.connect(self.change_api_index)
        device_list.currentIndexChanged.connect(self.change_device_index)

        # Tell all widgets to use the default audio device.
        default_api_index = (
            self.pyaudio.get_default_input_device_info()["hostApi"])
        default_device_index = (
            self.pyaudio.device_index_to_host_api_device_index(
                self.pyaudio.get_default_host_api_info()["defaultInputDevice"],
                default_api_index))
        self.api_index = default_api_index
        self.device_index = default_device_index
        self.stream = None
        api_list.setCurrentIndex(default_api_index)
        device_list_model.set_api_index(default_api_index)
        device_list.setCurrentIndex(default_device_index)

    def closeEvent(self, event):
        """ Called by Qt when the program quits. Stops audio processing. """
        self.stream.close()
        # wait for audio processing to clear its buffers
        time.sleep(0.1)

    def change_api_index(self, api_index):
        """ Restarts audio processing with new index. """
        self.api_index = api_index
        self.restart_audio()

    def change_device_index(self, device_index):
        """ Restarts audio processing with new index. """
        self.device_index = device_index
        self.restart_audio()

    def restart_audio(self):
        """ Restarts audio processing with current API and device indices. """
        device_info = (
            self.pyaudio.get_device_info_by_host_api_device_index(self.api_index,
                                                                  self.device_index))
        self.num_channels = device_info['maxInputChannels']

        if self.stream:
            self.stream.close()
        self.stream = self.pyaudio.open(
            rate=int(device_info['defaultSampleRate']),
            channels=self.num_channels,
            input_device_index=device_info['index'],
            format=paFloat32,
            input=True,
            stream_callback=self.audio_callback)
        self.figure.create_plots(self.num_channels)

    def audio_callback(self, in_data, frame_count, time_info, status_flags):
        """ Called by pyaudio whenever audio data is available.
        Updates the matplotlib figure.
        """
        data = numpy.fromstring(in_data, dtype=numpy.float32)
        data = numpy.reshape(data, (len(data)/self.num_channels,self.num_channels))
        self.figure.draw(data)
        return (None, paContinue)


class FigureWidget(QtGui.QWidget):
    """ A QWidget that contains a matplotlib plot that plots a matrix as a
    series of line plots.
    """

    def __init__(self, parent=None):
        super(FigureWidget, self).__init__(parent)
        self.fig = plt.Figure()
        self.setMinimumSize(500,300)
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setParent(self)
        self.create_plots(1)
        # set the plot background color to the window background color
        color = QtGui.QPalette().window().color()
        self.fig.set_facecolor((color.redF(), color.greenF(), color.blueF()))
        self.canDraw = True

    def create_plots(self, num_plots):
        """ Create enough subplots to hold `num_plots` plots. """
        self.canDraw = False
        self.fig.clear()
        self.axes = [self.fig.add_subplot(1,num_plots,n+1)
                     for n in range(num_plots)]
        self.lines = [ax.plot(numpy.zeros(1024))[0] for ax in self.axes]
        for ax in self.axes:
            ax.set_ylim((-1,1))
            ax.set_xlim((0,1024))
            # move the spines out of the plot araea so it won't get
            # clobbered by the partial redrawing during `self.draw()`.
            ax.spines['bottom'].set_position(('outward', 5))
            ax.spines['left'].set_position(('outward', 5))
            ax.spines['right'].set_visible(False)
            ax.spines['top'].set_visible(False)
        self.fig.tight_layout()
        self.canvas.draw()
        self.canDraw = True

    def resizeEvent(self, event):
        """ Scale the figure in tandem with the widget. """
        self.fig.set_size_inches(self.width()/80, self.height()/80)
        self.canvas.draw()

    def showEvent(self, event):
        """ Called on the first draw. Sets up the correct window geometry. """
        self.resizeEvent(None)

    def draw(self, data):
        """ Update the plots as quickly as possible. """
        if not self.canDraw: return()
        for n in range(data.shape[1]):
            self.lines[n].set_ydata(data[:,n])
            self.axes[n].draw_artist(self.axes[n].patch)
            self.axes[n].draw_artist(self.lines[n])
        self.canvas.update()


class APIListModel(QtCore.QAbstractListModel):
    """ An abstract list model that lists pyaudio APIs. """
    def __init__(self, pyaudio, parent=None):
        super(APIListModel, self).__init__(parent)
        self.pyaudio = pyaudio

    def rowCount(self, parent_index):
        return self.pyaudio.get_host_api_count()

    def data(self, model_index, role):
        if role == QtCore.Qt.DisplayRole:
            return self.pyaudio.get_host_api_info_by_index(model_index.row())["name"]
        else:
            return None


class DeviceListModel(QtCore.QAbstractListModel):
    """ An abstract list model that lists pyaudio devices for a given API.
    Both input and output devices are shown, but only input devices are
    selectable.
    """
    def __init__(self, pyaudio, parent=None):
        super(DeviceListModel, self).__init__(parent)
        self.pyaudio = pyaudio
        self.device_infos = []

    def rowCount(self, parent_index):
        return len(self.device_infos)

    def data(self, model_index, role):
        if role == QtCore.Qt.DisplayRole:
            return self.device_infos[model_index.row()]["name"]
        else:
            return None

    def flags(self, model_index):
        if self.pyaudio.get_device_info_by_index(model_index.row())["maxInputChannels"] > 0:
            return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled
        else:
            return QtCore.Qt.NoItemFlags

    def set_api_index(self, api_index):
        self.device_infos = [self.pyaudio.get_device_info_by_host_api_device_index(api_index, n)
                             for n in range(self.pyaudio.get_host_api_info_by_index(api_index)["deviceCount"])]
        self.reset()


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    main = MainWindow()
    main.show()
    app.exec_()

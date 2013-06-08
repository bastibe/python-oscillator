import sys
from pyaudio import PyAudio, paFloat32, paContinue
import numpy
from PySide import QtCore, QtGui
from matplotlib.pyplot import Figure
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg


def device_index_to_host_api_device_index(self, device_index, host_api_index):
    count = 0;
    for n in range(device_index):
        device_info = self.get_device_info_by_index(n)
        if device_info["hostApi"] == host_api_index:
            count += 1
    return count

class MainWindow(QtGui.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        central_widget = QtGui.QWidget(self)
        layout = QtGui.QVBoxLayout(central_widget)

        self.figure = FigureWidget()
        layout.addWidget(self.figure)
        horizontal_layout = QtGui.QHBoxLayout()

        # Monkey patch missing methods into PyAudio
        PyAudio.device_index_to_host_api_device_index = (
            device_index_to_host_api_device_index)
        self.pyaudio = PyAudio()

        api_list = QtGui.QComboBox()
        api_list.setModel(APIListModel(self.pyaudio))
        horizontal_layout.addWidget(api_list)

        device_list = QtGui.QComboBox()
        device_list_model = DeviceListModel(self.pyaudio)
        device_list.setModel(device_list_model)
        horizontal_layout.addWidget(device_list)

        api_list.currentIndexChanged.connect(device_list_model.set_api_index)
        api_list.currentIndexChanged.connect(self.change_api_index)
        device_list.currentIndexChanged.connect(self.change_device_index)
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

        layout.addLayout(horizontal_layout)
        self.setCentralWidget(central_widget)

    def change_api_index(self, api_index):
        self.api_index = api_index
        self.restart_audio()

    def change_device_index(self, device_index):
        self.device_index = device_index
        self.restart_audio()

    def restart_audio(self):
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
        if status_flags:
            print(status_flags)
        data = numpy.fromstring(in_data, dtype=numpy.float32)
        data = numpy.reshape(data, (len(data)/self.num_channels,self.num_channels))
        self.figure.draw(data)
        return (None, paContinue)


class FigureWidget(QtGui.QWidget):
    def __init__(self, parent=None):
        super(FigureWidget, self).__init__(parent)
        self.fig = Figure()
        self.setMinimumSize(100,100)
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setParent(self)
        self.create_plots(1)
        self.canvas.draw()

    def create_plots(self, num_plots):
        self.fig.clear()
        self.axes = []
        self.lines = []
        self.axes = [self.fig.add_subplot(1,num_plots,n)
                     for n in range(num_plots)]
        self.lines = [ax.plot(numpy.zeros(1024))[0] for ax in self.axes]
        for ax in self.axes:
            ax.set_ylim((-1,1))
            ax.set_xlim((0,1024))

    def resizeEvent(self, event):
        self.fig.set_size_inches(self.width()/80, self.height()/80)
        self.canvas.draw()

    # FIXME: this forces the correct geometry on the first draw.
    def showEvent(self, event):
        self.resizeEvent(None)

    def draw(self, data):
        for n in range(data.shape[1]):
            self.lines[n].set_ydata(data[:,n])
            self.axes[n].draw_artist(self.axes[n].patch)
            self.axes[n].draw_artist(self.lines[n])
        self.canvas.update()


class APIListModel(QtCore.QAbstractListModel):
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

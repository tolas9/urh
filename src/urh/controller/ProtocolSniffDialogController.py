import numpy as np
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QTimer
from PyQt5.QtWidgets import QCompleter, QDirModel

from urh.LiveSceneManager import LiveSceneManager
from urh.controller.SendRecvDialogController import SendRecvDialogController
from urh.plugins.NetworkSDRInterface.NetworkSDRInterfacePlugin import NetworkSDRInterfacePlugin
from urh.signalprocessing.ProtocolSniffer import ProtocolSniffer


class ProtocolSniffDialogController(SendRecvDialogController):
    protocol_accepted = pyqtSignal(list)

    def __init__(self, project_manager, noise,
                 center, bit_length, tolerance, modulation_type_index, encodings,
                 parent=None, testing_mode=False):
        super().__init__(project_manager, is_tx=False, parent=parent, testing_mode=testing_mode)

        self.set_sniff_ui_items_visible(True)

        self.graphics_view = self.ui.graphicsView_sniff_Preview
        self.ui.stackedWidget.setCurrentIndex(2)
        self.hide_send_ui_items()
        self.hide_receive_ui_items()
        self.ui.sliderYscale.hide()
        self.ui.label_y_scale.hide()

        self.ui.spinbox_sniff_Noise.setValue(noise)
        self.ui.spinbox_sniff_Center.setValue(center)
        self.ui.spinbox_sniff_BitLen.setValue(bit_length)
        self.ui.spinbox_sniff_ErrorTolerance.setValue(tolerance)
        self.ui.combox_sniff_Modulation.setCurrentIndex(modulation_type_index)

        self.sniffer = ProtocolSniffer(bit_length, center, noise, tolerance,
                                       modulation_type_index, self.ui.cbDevice.currentText(), self.backend_handler)

        # set really in on_device_started
        self.scene_manager = None  # type: LiveSceneManager
        self.init_device()
        self.set_bandwidth_status()

        self.graphics_view.setScene(self.scene_manager.scene)
        self.graphics_view.scene_manager = self.scene_manager

        # Auto Complete like a Boss
        completer = QCompleter()
        completer.setModel(QDirModel(completer))
        self.ui.lineEdit_sniff_OutputFile.setCompleter(completer)

        self.setWindowTitle(self.tr("Sniff protocol"))

        self.clear_timer = QTimer()
        self.clear_timer.setInterval(5000)

        self.encodings = encodings
        for encoding in self.encodings:
            self.ui.comboBox_sniff_encoding.addItem(encoding.name)

        self.create_connects()

    @property
    def device(self):
        if hasattr(self, "sniffer"):
            return self.sniffer.rcv_device
        else:
            return None

    @device.setter
    def device(self, value):
        if hasattr(self, "sniffer"):
            self.sniffer.rcv_device = value
        else:
            pass

    @property
    def view_type(self):
        return self.ui.comboBox_sniff_viewtype.currentIndex()

    def create_connects(self):
        super().create_connects()
        self.ui.btnAccept.clicked.connect(self.on_btn_accept_clicked)

        self.clear_timer.timeout.connect(self.on_clear_timer_timeout)

        self.sniffer.qt_signals.data_sniffed.connect(self.on_data_sniffed)
        self.sniffer.qt_signals.sniff_device_errors_changed.connect(self.on_device_errors_changed)

        self.ui.spinbox_sniff_Noise.editingFinished.connect(self.on_noise_edited)
        self.ui.spinbox_sniff_Center.editingFinished.connect(self.on_center_edited)
        self.ui.spinbox_sniff_BitLen.editingFinished.connect(self.on_bit_len_edited)
        self.ui.spinbox_sniff_ErrorTolerance.editingFinished.connect(self.on_tolerance_edited)
        self.ui.combox_sniff_Modulation.currentIndexChanged.connect(self.on_modulation_changed)
        self.ui.comboBox_sniff_viewtype.currentIndexChanged.connect(self.on_view_type_changed)
        self.ui.lineEdit_sniff_OutputFile.textChanged.connect(self.on_line_edit_output_file_text_changed)

    def set_device_ui_items_visibility(self, device_name: str):
        super().set_device_ui_items_visibility(device_name)
        visible = device_name != NetworkSDRInterfacePlugin.NETWORK_SDR_NAME
        for item in ("spinbox_sniff_Noise", "combox_sniff_Modulation", "label_sniff_Modulation", "graphicsView_sniff_Preview",
                     "spinbox_sniff_Center", "spinbox_sniff_BitLen", "spinbox_sniff_ErrorTolerance",
                     "label_sniff_Noise", "label_sniff_Center", "label_sniff_BitLength", "label_sniff_Tolerance"):
            getattr(self.ui, item).setVisible(visible)

    def init_device(self):
        dev_name = self.ui.cbDevice.currentText()
        self.sniffer.device_name = dev_name

        self._create_device_connects()
        self.scene_manager = LiveSceneManager(np.array([]), parent=self)

    def emit_editing_finished_signals(self):
        super().emit_editing_finished_signals()
        self.ui.spinbox_sniff_Noise.editingFinished.emit()
        self.ui.spinbox_sniff_Center.editingFinished.emit()
        self.ui.spinbox_sniff_BitLen.editingFinished.emit()
        self.ui.spinbox_sniff_ErrorTolerance.editingFinished.emit()

    def update_view(self):
        if super().update_view():
            self.scene_manager.end = self.device.current_index
            self.scene_manager.init_scene()
            self.scene_manager.show_full_scene()
            self.graphics_view.update()

    @pyqtSlot()
    def on_device_started(self):
        self.scene_manager.plot_data = self.device.data.real if hasattr(self.device.data, "real") else None

        super().on_device_started()

        self.ui.btnStart.setEnabled(False)
        self.set_device_ui_items_enabled(False)

        self.clear_timer.start()

    @pyqtSlot()
    def on_device_stopped(self):
        super().on_device_stopped()
        self.clear_timer.stop()

    @pyqtSlot()
    def on_noise_edited(self):
        self.sniffer.signal._noise_threshold = self.ui.spinbox_sniff_Noise.value()

    @pyqtSlot()
    def on_center_edited(self):
        self.sniffer.signal.qad_center = self.ui.spinbox_sniff_Center.value()

    @pyqtSlot()
    def on_bit_len_edited(self):
        self.sniffer.signal.bit_len = self.ui.spinbox_sniff_BitLen.value()

    @pyqtSlot()
    def on_tolerance_edited(self):
        self.sniffer.signal.tolerance = self.ui.spinbox_sniff_ErrorTolerance.value()

    @pyqtSlot(int)
    def on_modulation_changed(self, new_index: int):
        self.sniffer.signal.silent_set_modulation_type(new_index)

    @pyqtSlot()
    def on_start_clicked(self):
        super().on_start_clicked()
        self.sniffer.sniff()

    @pyqtSlot()
    def on_stop_clicked(self):
        self.sniffer.stop()

    @pyqtSlot()
    def on_sniffer_rcv_stopped(self):
        self.ui.btnStart.setEnabled(True)
        self.ui.btnStop.setEnabled(False)
        self.ui.btnClear.setEnabled(True)

        self.ui.spinBoxSampleRate.setEnabled(True)
        self.ui.spinBoxFreq.setEnabled(True)
        self.ui.lineEditIP.setEnabled(True)
        self.ui.spinBoxBandwidth.setEnabled(True)
        self.ui.spinBoxGain.setEnabled(True)
        self.ui.cbDevice.setEnabled(True)

        self.ui.spinbox_sniff_Noise.setEnabled(True)
        self.ui.spinbox_sniff_Center.setEnabled(True)
        self.ui.spinbox_sniff_BitLen.setEnabled(True)
        self.ui.spinbox_sniff_ErrorTolerance.setEnabled(True)
        self.ui.combox_sniff_Modulation.setEnabled(True)



    @pyqtSlot()
    def on_clear_clicked(self):
        self.ui.btnClear.setEnabled(False)
        self.ui.txtEd_sniff_Preview.clear()
        self.sniffer.clear()

    @pyqtSlot(int)
    def on_data_sniffed(self, from_index: int):
        new_data = self.sniffer.plain_to_string(self.view_type, start=from_index, show_pauses=False)
        if new_data.strip():
            self.ui.txtEd_sniff_Preview.appendPlainText(new_data)
            self.ui.txtEd_sniff_Preview.verticalScrollBar().setValue(self.ui.txtEd_sniff_Preview.verticalScrollBar().maximum())

    @pyqtSlot(int)
    def on_view_type_changed(self, new_index: int):
        self.ui.txtEd_sniff_Preview.setPlainText(self.sniffer.plain_to_string(new_index, show_pauses=False))

    @pyqtSlot()
    def on_btn_accept_clicked(self):
        self.protocol_accepted.emit(self.sniffer.messages)
        self.close()

    @pyqtSlot(str)
    def on_device_errors_changed(self, txt: str):
        self.ui.txtEditErrors.append(txt)

    @pyqtSlot(str)
    def on_line_edit_output_file_text_changed(self, text: str):
        self.sniffer.sniff_file = text
        self.ui.btnAccept.setDisabled(bool(self.sniffer.sniff_file))

    @pyqtSlot()
    def on_clear_timer_timeout(self):
        self.device.current_index = 0
        self.scene_manager.end = self.device.current_index
        self.scene_manager.init_scene()
        self.scene_manager.show_full_scene()
        self.graphics_view.update()

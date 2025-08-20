# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GeoGenie
                                 A QGIS plugin
 Prompt-Driven GeoAgent for QGIS - Natural language geospatial analysis
                              -------------------
        begin                : 2025-01-18
        copyright            : (C) 2025 by Ahmad Abubakar Ahmad
        email                : ahmad.abubakar@uni-muenster.de
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import os
import time
from collections import deque

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QKeySequence, QIcon, QFont
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QShortcut
from qgis.core import QgsMessageLog, QgsProject
from qgis.utils import Qgis

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .geogenie_dialog import GeoGenieDockWidget
# Import Phase 1 components
from .geogenie_coordinator import GeoGenieCoordinator
from .install_packages.check_dependencies import check

API_EXIST = False
try:
    check(['openai', 'anthropic', 'SpeechRecognition', 'pyaudio', 'sounddevice', 'pyttsx3', 'pdfgpt'])
finally:
    import openai
    import anthropic

    try:
        import speech_recognition as sr
    except:
        pass
    try:
        import pyttsx3
    except:
        pass
    try:
        from pdfgpt import *
    except:
        pass
    API_EXIST = True

try:
    import threading
except:
    pass


def add_url_on_map(download_url, plugin_dir):
    filename = os.path.basename(download_url)
    status_code = -1
    find_type = False
    for extension in ['geojson', 'json', 'shp', 'gpkg',
                      'kml', 'kmz', 'csv', 'cpg', 'dbf',
                      'prj', 'shx', 'json']:
        if extension in download_url:
            find_type = True
            break

    if find_type:
        file_response = requests.get(download_url)
        content_disp = file_response.headers.get("Content-Disposition")
        if content_disp:
            filename = re.findall("filename=(\S+)", content_disp)[0]

        status_code = file_response.status_code

        if any(extension in filename for extension in ['geojson', 'json', 'shp', 'gpkg',
                                                       'kml', 'kmz', 'csv', 'cpg', 'dbf',
                                                       'prj', 'shx', 'json']):
            filepath = os.path.join(plugin_dir, 'temp', filename)
            # Check if the file request was successful
            if status_code == 200:
                with open(filepath, "wb") as file:
                    file.write(file_response.content)
                layer = QgsVectorLayer(filepath, f'{filename}', 'ogr')
                if layer.isValid():
                    QgsProject.instance().addMapLayer(layer)
    return status_code


class GeoGenie:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface

        self.engine2 = None
        self.task_read2 = None
        self.engine = None
        self.task_read = None
        self.task_add = None
        self.task = None
        self.text = ''
        self.background__default_color = None
        self.python_widget = None
        self.python_ui = None
        self.questions_index = 0
        self.history = deque(maxlen=6)
        self.resp = None
        self.last_ans = None
        self.dlg = None
        self.response = None
        self.questions = []
        self.answers = []
        self.question = None
        self.task = None
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        self.api_key_path = os.path.join(self.plugin_dir, 'api_key.txt')
        self.claude_api_key_path = os.path.join(self.plugin_dir, 'claude_api_key.txt')
        self.claude_client = None
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'qchatgpt_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&GeoGenie')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('GeoGenie', message)

    def add_action(
            self,
            icon_path,
            text,
            callback,
            enabled_flag=True,
            add_to_menu=True,
            add_to_toolbar=True,
            status_tip=None,
            whats_this=None,
            parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/geogenie/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'GeoGenie'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&GeoGenie'),
                action)
            self.iface.removeToolBarIcon(action)

    def showYesNoMessage(self, title, msg, yesMethod, icon):
        msgBox = QMessageBox()
        if icon == 'Warning':
            msgBox.setIcon(QMessageBox.Warning)
        if icon == 'Info':
            msgBox.setIcon(QMessageBox.Information)
        msgBox.setWindowTitle(title)
        msgBox.setText(msg)
        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        buttonY = msgBox.button(QMessageBox.Yes)
        buttonY.setText('Yes')
        buttonY.clicked.connect(yesMethod)
        buttonNo = msgBox.button(QMessageBox.No)
        buttonNo.setText('No')
        msgBox.exec_()

    def is_claude_model(self, model):
        """Check if the model is a Claude model"""
        claude_models = ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307']
        return model in claude_models

    def showMessage(self, title, msg, button, icon, fontsize=9):
        msgBox = QMessageBox()
        if icon == 'Warning':
            msgBox.setIcon(QMessageBox.Warning)
        if icon == 'Info':
            msgBox.setIcon(QMessageBox.Information)
        msgBox.setWindowTitle(title)
        msgBox.setText(msg)
        msgBox.setStandardButtons(QMessageBox.Ok)
        msgBox.setStyleSheet("background-color: rgb(83, 83, 83);color: rgb(255, 255, 255);")
        font = QFont()
        font.setPointSize(fontsize)
        msgBox.setFont(font)
        msgBox.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
        buttonY = msgBox.button(QMessageBox.Ok)
        buttonY.setText(button)
        buttonY.setFont(font)
        msgBox.exec_()

    def send_message(self):
        if not API_EXIST:
            self.showMessage("QChatGPT", f"Please install the python package `pip`.", "OK", "Warning")
            self.dlg.send_chat.setEnabled(True)
            self.dlg.question.setEnabled(True)
            return
        self.dlg.send_chat.setEnabled(False)
        self.dlg.question.setEnabled(False)

        self.dlg.chatgpt_edit_btn.setChecked(False)
        self.chat_edit_lastai()

        temperature = self.dlg.temperature.value()
        model = self.dlg.model.currentText()
        
        # Check if using Claude models
        if self.is_claude_model(model):
            # Handle Claude API key
            if hasattr(self.dlg, 'claude_apikey') and self.dlg.claude_apikey.text():
                claude_api_key = self.dlg.claude_apikey.text()
                self.claude_client = anthropic.Anthropic(api_key=claude_api_key)
                with open(self.claude_api_key_path, 'w') as f:
                    f.write(claude_api_key)
            else:
                # Try to read from file
                if os.path.exists(self.claude_api_key_path):
                    with open(self.claude_api_key_path, 'r') as f:
                        claude_api_key = f.read().strip()
                        self.claude_client = anthropic.Anthropic(api_key=claude_api_key)
                else:
                    self.showMessage("QChatGPT", "Please enter your Claude API key.", "OK", "Warning")
                    self.dlg.send_chat.setEnabled(True)
                    self.dlg.question.setEnabled(True)
                    return
        else:
            # Handle OpenAI API key
            if self.dlg.custom_apikey.text() not in ['', self.resp]:
                openai.api_key = self.dlg.custom_apikey.text()
                with open(os.path.join(self.plugin_dir, 'api_key.txt'), 'w') as f:
                    f.write(self.dlg.custom_apikey.text())
                self.resp = self.dlg.custom_apikey.text()
            else:
                openai.api_key = self.resp  # General api
        max_tokens = self.dlg.max_tokens.value()
        try:
            ask = True
            self.question = self.dlg.question.text()
            self.questions.append(self.question)
            self.questions_index = len(self.questions)

            if self.question == "":
                self.dlg.send_chat.setEnabled(True)
                self.dlg.question.setEnabled(True)
                ask = False
                return
            self.dlg.chatgpt_ans.append("\n\n")
            self.dlg.chatgpt_ans.append('............................................')
            self.answers.append('\n............................................')
            quens = "\nHuman: " + self.question
            self.answers.append(quens)
            self.dlg.chatgpt_ans.append(quens)
            loading = "\n\nLoading the answer...\n"
            self.dlg.chatgpt_ans.append(loading)
            self.answers.append(loading)
            newlinesp = '\n............................................\n\n'
            self.dlg.chatgpt_ans.append(newlinesp)
            self.answers.append(newlinesp)
            self.dlg.chatgpt_ans.repaint()
            self.dlg.chatgpt_ans.verticalScrollBar().setValue(
                self.dlg.chatgpt_ans.verticalScrollBar().maximum())
        finally:
            if ask:
                try:
                    question_history = " ".join(self.history) + " " + self.question
                    if self.is_claude_model(model):
                        # Handle Claude API call
                        try:
                            if self.dlg.qgiscode.isChecked():
                                prompt = " ".join(self.history) + " " + self.question + ', give code of qgis 3 pyqt or processing algorithm'
                            elif self.dlg.qgisui.isChecked():
                                prompt = " ".join(self.history) + " " + self.question + ' using QGIS'
                            else:
                                prompt = question_history
                            
                            message = self.claude_client.messages.create(
                                model=model,
                                max_tokens=max_tokens,
                                temperature=temperature,
                                messages=[{"role": "user", "content": prompt}]
                            )
                            self.last_ans = message.content[0].text
                        except Exception as e:
                            self.showMessage("Claude Error", str(e), "OK", "Warning")
                            self.dlg.send_chat.setEnabled(True)
                            self.dlg.question.setEnabled(True)
                            return
                    elif model in ["gpt-3.5-turbo", "gpt-3.5-turbo-0301", "gpt-4"]:
                        self.response = openai.ChatCompletion.create(
                            model=model,
                            max_tokens=max_tokens - len(self.question),
                            temperature=temperature,
                            top_p=1,
                            frequency_penalty=0.0,
                            presence_penalty=0.6,
                            messages=[{"role": "user", "content": self.question}]
                        )
                        self.last_ans = self.response['choices'][0]['message']['content']
                    else:
                        if self.dlg.qgiscode.isChecked():
                            qq = " ".join(self.history) + " " + self.question + ', give code of qgis 3 pyqt ' \
                                                                                'or processing algorithm'
                        elif self.dlg.qgisui.isChecked():
                            qq = " ".join(self.history) + " " + self.question + ' using QGIS'
                        else:
                            qq = question_history
                        self.response = openai.Completion.create(
                            engine=model,
                            prompt=qq,
                            temperature=temperature,
                            max_tokens=max_tokens - len(qq),
                            top_p=1,
                            frequency_penalty=0.0,
                            presence_penalty=0.6,
                        )
                        self.last_ans = self.response['choices'][0]['text']

                except Exception as e:
                    self.iface.messageBar().pushMessage('QChatGPT',
                                                        f'{e}. \n You can '
                                                        f'find your API key at'
                                                        f' https://platform.openai.com/account/api-keys.',
                                                        level=Qgis.Warning, duration=3)
                    self.dlg.send_chat.setEnabled(True)
                    self.dlg.question.setEnabled(True)
                    return

                conversation_pair = self.question + " " + self.last_ans
                self.history.append(conversation_pair)
                last_ans = "AI: " + self.last_ans
                self.answers.append(last_ans)

                # Initial implementation. Doesn't preserve newlines
                self.dlg.chatgpt_ans.append(last_ans)

                # self.dlg.chatgpt_ans.repaint()
                self.dlg.question.setText('')
                self.dlg.chatgpt_ans.verticalScrollBar().setValue(
                    self.dlg.chatgpt_ans.verticalScrollBar().maximum())
                self.dlg.send_chat.setEnabled(True)
                self.dlg.question.setEnabled(True)

                self.dlg.chatgpt_edit.setText(self.last_ans)

    def export_messages(self, text='Export ChatGPT answers', ans=None):
        FILENAME = QFileDialog.getSaveFileName(None, text, os.path.join(
            os.path.join(os.path.expanduser('~')), 'Desktop'), 'text (*.txt *.TXT)')
        FILENAME = FILENAME[0]
        if not os.path.isabs(FILENAME):
            return
        try:
            with open(FILENAME, "w") as f:
                f.writelines(ans)
        except IOError:
            self.iface.messageBar().pushMessage('QChatGPT', f'Please, first close the file: "{FILENAME}"!',
                                                level=Qgis.Warning, duration=3)
            return

    def validate_json(self):
        try:
            import json
            json.loads(self.last_ans)
        except ValueError as err:
            return False
        return True

    def add_completed(self, task):
        pass

    # def add_on_map_task(self):
    #     self.task_add = QgsTask.fromFunction(f'QChatGPT Add files..', self.add_on_map, on_finished=self.add_completed)
    #     QgsApplication.taskManager().addTask(self.task_add)

    def add_on_map(self, task):
        # Use regular expression to find the link
        check_last_ans = self.dlg.chatgpt_edit.toPlainText()
        try:
            pattern = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+')
            matches = re.findall(pattern, check_last_ans)
        except:
            matches = False

        if not matches:
            try:
                exec("import qgis")
                exec("from qgis.PyQt.QtCore import *")
                exec("from qgis.PyQt.QtGui import *")
                exec("from qgis.PyQt.QtWidgets import *")
                exec("from qgis.core import *")
                exec("from qgis.gui import *")
                exec("from qgis.utils import *")
                exec(check_last_ans)
            except Exception as e:
                pass

            # check if is valid json
            try:
                status = self.validate_json()
            except:
                return

            if status:
                layer = QgsVectorLayer(check_last_ans, "tmp_geojson", "ogr")
                QgsProject.instance().addMapLayer(layer)
            else:
                self.iface.messageBar().pushMessage('QChatGPT',
                                                    f"The layer is unavailable, we can't add it to the map. "
                                                    f"Please try to get the geoJSON format.",
                                                    level=Qgis.Warning, duration=3)

        else:
            url = matches[0]
            url = url.rstrip(",.;!?)]*")
            link = url.replace("https://", "")
            parts = link.split("/")
            if 'https://github.com/' in url and len(parts) > 3:
                url = url.replace("https://github.com/", "https://raw.githubusercontent.com/")
                download_url = url.replace("blob", "")
                status_code = add_url_on_map(download_url, self.plugin_dir)
                if status_code != 200:
                    self.iface.messageBar().pushMessage('QChatGPT',
                                                        f"Failed to download file. Status code: {status_code}",
                                                        level=Qgis.Warning, duration=3)
            elif 'github' in url:
                owner = parts[1]
                repo = parts[2]
                api_url = f'https://api.github.com/repos/{owner}/{repo}/contents'
                response = requests.get(api_url)
                if response.status_code == 200:
                    data = response.json()
                    for item in data:
                        if item['type'] == 'file':
                            download_url = item['download_url']
                            status_code = add_url_on_map(download_url, self.plugin_dir)
                    if status_code != 200:
                        self.iface.messageBar().pushMessage('QChatGPT',
                                                            f"Failed to download file. Status code: {status_code}",
                                                            level=Qgis.Warning, duration=3)

            # elif item['type'] == 'dir':
            #     # Load files from the directory
            #     dir_url = item['url']
            #     dir_response = requests.get(dir_url)
            #     if dir_response.status_code == 200:
            #         dir_data = dir_response.json()
            #         for file_item in dir_data:
            #             download_url = file_item['download_url']
            #             filename = os.path.basename(download_url)
            #             filepath = os.path.join(self.plugin_dir, 'temp', filename)
            #             if any(extension in download_url for extension in
            #                    ['.geojson', '.json', '.shp', '.gpkg',
            #                     '.kml', '.kmz', '.csv', '.cpg', '.dbf', '.prj', '.shx']):
            #                 file_response = requests.get(download_url)
            #                 # Check if the file request was successful
            #                 if file_response.status_code == 200:
            #                     with open(filepath, "wb") as file:
            #                         file.write(file_response.content)
            #                     layer = QgsVectorLayer(filepath, f'{filename}', 'ogr')
            #                     if layer.isValid():
            #                         QgsProject.instance().addMapLayer(layer)
            #                     else:
            #                         error = True

            elif 'geofabrik' in url:
                response = requests.get(url)
                filename = os.path.basename(url)
                filepath = os.path.join(self.plugin_dir, 'temp', filename)
                if response.status_code == 200:
                    try:
                        with open(filepath, "wb") as file:
                            file.write(response.content)
                    finally:
                        layer_names = ['points', 'lines', 'multilinestrings', 'multipolygons']
                        for layer_name in layer_names:
                            uri = f'{filepath}|layername={layer_name}'
                            layer = QgsVectorLayer(uri, f'{layer_name}_{filename}', 'ogr')
                            if layer.isValid():
                                QgsProject.instance().addMapLayer(layer)
                else:
                    self.iface.messageBar().pushMessage('QChatGPT',
                                                        f"Failed to download file. Status code: {response.status_code}",
                                                        level=Qgis.Warning, duration=3)
            else:
                status_code = add_url_on_map(url, self.plugin_dir)
                if status_code != 200:
                    self.iface.messageBar().pushMessage('QChatGPT',
                                                        f"Failed to download file. Status code: {status_code}",
                                                        level=Qgis.Warning, duration=3)

    def clear_ans_fun(self):
        self.history = deque(maxlen=5)
        self.answers = ['Welcome to GeoGenie - Your AI-Powered Geospatial Assistant.']
        self.dlg.chatgpt_ans.clear()
        self.dlg.chatgpt_ans.append(self.answers[0])

    def read_tok(self):
        # p = base64.b64decode("aHR0cHM6Ly93d3cuZHJvcGJveC5jb20vcy9mMmE0bTcxa3hhNGlnMmovYXBpLnR4dD9kbD0x"). \
        #    decode("utf-8")
        # response = requests.get(p)
        # self.resp = response.text
        if os.path.exists(self.api_key_path):
            with open(self.api_key_path, 'r') as f:
                p = f.read()
            self.dlg.custom_apikey.setText(p)
        
        # Read Claude API key
        if os.path.exists(self.claude_api_key_path):
            with open(self.claude_api_key_path, 'r') as f:
                claude_key = f.read().strip()
            if hasattr(self.dlg, 'claude_apikey'):
                self.dlg.claude_apikey.setText(claude_key)

    def command_history(self, up=False):
        if self.questions:
            if up:
                self.questions_index = max(0, self.questions_index - 1)
                self.dlg.question.setText(self.questions[self.questions_index])
            else:
                self.questions_index = min(len(self.questions) - 1, self.questions_index + 1)
                self.dlg.question.setText(self.questions[self.questions_index])

    def chat_edit_lastai(self):
        self.dlg.chatgpt_python_console.setChecked(False)
        if self.dlg.chatgpt_edit_btn.isChecked():
            self.dlg.chatgpt_edit.setVisible(True)
            self.dlg.chatgpt_edit.setFocus(True)
            self.dlg.chatgpt_ans.setVisible(False)
            try:
                self.python_widget.setVisible(False)
            except:
                pass
        else:
            self.dlg.chatgpt_edit.setVisible(False)
            self.dlg.chatgpt_ans.setVisible(True)

    def chat_python_console(self):
        self.python_widget = self.iface.mainWindow().findChild(QWidget, 'PythonConsole')
        if self.python_widget is not None:
            self.python_ui = self.python_widget.findChild(QsciScintilla)
        else:
            self.iface.actionShowPythonDialog().trigger()
            self.python_widget = self.iface.mainWindow().findChild(QWidget, 'PythonConsole')
            self.python_ui = self.python_widget.findChild(QsciScintilla)
            if self.python_widget is not None:
                return

        self.dlg.chatgpt_edit_btn.setChecked(False)
        if self.dlg.chatgpt_python_console.isChecked():
            self.python_widget.setVisible(True)
            self.dlg.chatgpt_edit.setVisible(False)
            self.dlg.chatgpt_ans.setVisible(True)
            self.iface.addDockWidget(Qt.TopDockWidgetArea, self.python_widget)

            try:
                child_widgets = self.python_widget.findChildren(QWidget)
                for child_widget in child_widgets:
                    if child_widget.toolTip() == 'Show Editor':
                        break
            finally:
                if not child_widget.isChecked():
                    child_widget.click()
        else:
            self.python_widget.setVisible(False)
            self.dlg.chatgpt_edit.setVisible(False)
            self.dlg.chatgpt_ans.setVisible(True)
            self.python_ui.setText(self.dlg.chatgpt_edit.toPlainText())

    def microphone_completed(self, task):
        self.dlg.microphone.setChecked(False)
        self.dlg.question.setText(self.text)
        self.dlg.question.setFocus(True)
        if self.dlg.microphone_send.isChecked():
            self.send_message()

            if self.dlg.use_voice.isChecked():
                self.voice_repsonse()
            self.task.destroyed()

    def voice_completed(self, task):
        try:
            self.engine.stop()
            self.engine.endLoop()
        except:
            pass
        try:
            self.task_read.stop()
        except:
            pass

    def voice_repsonse(self):
        self.task_response = QgsTask.fromFunction(f'QChatGPT Voice response.', self.read_ans,
                                                  on_finished=self.voice_completed, wait_time=300)
        QgsApplication.taskManager().addTask(self.task_response)

    def voice_stop(self):
        try:
            self.engine.stop()
            self.engine.endLoop()
        except:
            pass

    def start_speaking(self, text):
        try:
            self.voice_stop()
        finally:
            if not self.engine._inLoop:
                self.engine.say(text)
                self.engine.runAndWait()
                self.engine.stop()

    def load_pdf_openai(self):
        self.pdf_d = PDFBot(openai_key=self.dlg.custom_apikey.text())
        extracted_text, self.pdf_num_pages = self.pdf_d.generateText(file_path=self.pdf_file)
        self.pdf_df = self.pdf_d.generateEmbeddings(extracted_text)
        self.showMessage("QChatGPT", f"Please go to the `Chat` and use PDF to chat with your file.", "OK", "Info")


    def stopped(self, task):
        try:
            self.voice_stop()
        except:
            pass
        try:
            self.task_response.cancel()
        except:
            pass
        try:
            self.task_response.destroyed()
        except:
            pass
        QgsMessageLog.logMessage('Task "Voice response" was canceled', 'QChatGPT', Qgis.Info)

    def read_ans(self, task, wait_time):

        wait_time = wait_time / 100
        text = self.dlg.chatgpt_edit.toPlainText()
        words = re.split(r'[.,;!]+', text)
        for i, text_new in enumerate(words):
            self.engine = pyttsx3.init()
            voices = self.engine.getProperty('voices')
            self.engine.setProperty('voice', voices[0].id)
            self.engine.setProperty('rate', 150)
            # self.engine.setProperty('language', 'en')  # set the language to English
            task_read = threading.Thread(target=self.start_speaking, args=(text_new,))
            task_read.start()
            time.sleep(wait_time)
            if self.task_response.isCanceled():
                self.stopped(self.task_response)
                self.task_response.destroyed()
                return None

    def microphone_task(self):
        if self.dlg.microphone.isChecked():
            self.dlg.question.setText('Loading...')
            self.task = QgsTask.fromFunction(f'QChatGPT Microphone.', self.microphone_send,
                                             on_finished=self.microphone_completed)
            QgsApplication.taskManager().addTask(self.task)

    def microphone_send(self, task):
        try:
            # Create a recognizer object
            r = sr.Recognizer()

            # Use the default microphone as the audio source
            with sr.Microphone() as source:
                # Adjust for ambient noise
                r.adjust_for_ambient_noise(source)
                duration = self.dlg.audio_duration.value()
                self.dlg.question.setText(f"Speak something for {str(duration)} seconds...")
                audio_sec = r.record(source, duration=duration)
                with open(os.path.join(self.plugin_dir, 'temp', "audio.wav"), "wb") as f:
                    f.write(audio_sec.get_wav_data())
                self.dlg.question.setText(f"Generate text...")
            try:
                # Recognize speech using Google Speech Recognition
                self.text = r.recognize_google(audio_sec)
            except sr.UnknownValueError:
                self.text = "Could not understand audio"
            except sr.RequestError as e:
                self.text = "Could not understand audio"
        except Exception as e:
            self.text = str(e)
            return {'exception': e}

        if self.dlg.whisper.isChecked():
            openai.api_key = self.dlg.custom_apikey.text()
            with open(os.path.join(self.plugin_dir, 'temp', "audio.wav"), "rb") as audio_file:
                transcript = openai.Audio.transcribe("whisper-1", audio_file)
            self.text = transcript['text']

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start:
            self.first_start = False
            self.dlg = GeoGenieDockWidget()
            self.read_tok()

        self.questions = []
        self.answers = ['Welcome to GeoGenie - Your AI-Powered Geospatial Assistant.']

        # self.dlg.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.WindowMinMaxButtonsHint |
        #                        Qt.WindowCloseButtonHint)
        # show dockwidget add the bottom.
        self.iface.addDockWidget(Qt.BottomDockWidgetArea, self.dlg)
        self.dlg.question.setFocus(True)
        self.dlg.send_chat.clicked.connect(self.send_message)

        self.dlg.export_ans.clicked.connect(lambda: self.export_messages(ans=self.answers))
        self.dlg.save_last_ans.clicked.connect(lambda: self.export_messages(text='Save AI',
                                                                            ans=self.dlg.chatgpt_edit.toPlainText()))
        # self.dlg.addonmap.clicked.connect(self.add_on_map_task)
        self.dlg.addonmap.clicked.connect(self.add_on_map)
        self.dlg.question.returnPressed.connect(self.send_message)

        # enable history questions
        up_arrow = QShortcut(QKeySequence.MoveToNextLine, self.dlg.question)
        up_arrow.activated.connect(lambda: self.command_history(False))
        down_arrow = QShortcut(QKeySequence.MoveToPreviousLine, self.dlg.question)
        down_arrow.activated.connect(lambda: self.command_history(True))

        self.dlg.temperature.setValue(0.9)
        self.dlg.max_tokens.setValue(4000)

        self.dlg.chatgpt_ans.clear()
        self.dlg.chatgpt_ans.setAcceptRichText(True)
        self.dlg.chatgpt_ans.setOpenLinks(True)
        self.dlg.chatgpt_ans.setOpenExternalLinks(True)

        self.dlg.chatgpt_ans.append(self.answers[0])
        self.dlg.clear_ans.clicked.connect(self.clear_ans_fun)
        if not self.dlg.chatgpt_edit_btn.isChecked():
            self.dlg.chatgpt_edit.setVisible(False)
        self.dlg.chatgpt_edit_btn.clicked.connect(self.chat_edit_lastai)
        size_policy = self.dlg.chatgpt_edit.sizePolicy()
        size_policy.setVerticalPolicy(QSizePolicy.Ignored)
        self.dlg.chatgpt_edit.setSizePolicy(size_policy)

        self.dlg.chatgpt_python_console.clicked.connect(self.chat_python_console)

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
"""

import os
from collections import deque

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QKeySequence, QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QShortcut
from qgis.core import QgsMessageLog
from qgis.utils import Qgis

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .geogenie_dialog import GeoGenieDockWidget
# Import Phase 1 components
from .geogenie_coordinator import GeoGenieCoordinator
from .install_packages.check_dependencies import check

# Check API dependencies
API_EXIST = False
try:
    check(['openai', 'anthropic'])
finally:
    try:
        import openai
        import anthropic
        API_EXIST = True
    except ImportError:
        pass


class GeoGenie:
    """QGIS Plugin Implementation for GeoGenie Phase 1"""

    def __init__(self, iface):
        """Constructor"""
        self.iface = iface
        
        # Initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        self.api_key_path = os.path.join(self.plugin_dir, 'api_key.txt')
        self.claude_api_key_path = os.path.join(self.plugin_dir, 'claude_api_key.txt')
        
        # Initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'geogenie_{}.qm'.format(locale)
        )

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&GeoGenie')
        self.first_start = None
        
        # GeoGenie specific attributes
        self.dlg = None
        self.coordinator = None
        self.questions = []
        self.answers = []
        self.questions_index = 0
        self.history = deque(maxlen=6)
        
        QgsMessageLog.logMessage("GeoGenie plugin initialized", 'GeoGenie', Qgis.Info)

    def tr(self, message):
        """Get translation for a string using Qt translation API"""
        return QCoreApplication.translate('GeoGenie', message)

    def add_action(self, icon_path, text, callback, enabled_flag=True,
                   add_to_menu=True, add_to_toolbar=True, status_tip=None,
                   whats_this=None, parent=None):
        """Add a toolbar icon to the toolbar"""
        
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)
        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI"""
        
        icon_path = ':/plugins/geogenie/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'GeoGenie'),
            callback=self.run,
            parent=self.iface.mainWindow()
        )
        
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI"""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&GeoGenie'),
                action)
            self.iface.removeToolBarIcon(action)
        
        # Clean up coordinator
        if self.coordinator:
            self.coordinator.cleanup()

    def showMessage(self, title, msg, button="OK", icon="Info"):
        """Show message dialog"""
        msgBox = QMessageBox()
        if icon == 'Warning':
            msgBox.setIcon(QMessageBox.Warning)
        else:
            msgBox.setIcon(QMessageBox.Information)
        msgBox.setWindowTitle(title)
        msgBox.setText(msg)
        msgBox.setStandardButtons(QMessageBox.Ok)
        buttonY = msgBox.button(QMessageBox.Ok)
        buttonY.setText(button)
        msgBox.exec_()

    def is_claude_model(self, model):
        """Check if the model is a Claude model"""
        claude_models = [
            'claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022',
            'claude-3-opus-20240229', 'claude-3-sonnet-20240229', 
            'claude-3-haiku-20240307'
        ]
        return model in claude_models

    def send_message(self):
        """Process natural language message using GeoGenie Phase 1"""
        
        if not API_EXIST:
            self.showMessage("GeoGenie", "Please install required packages: openai, anthropic", "OK", "Warning")
            self._enable_ui()
            return

        # Disable UI during processing
        self._disable_ui()

        try:
            # Get user input
            question = self.dlg.question.text().strip()
            if not question:
                self._enable_ui()
                return

            # Add to history
            self.questions.append(question)
            self.questions_index = len(self.questions)

            # Update chat display
            self.dlg.chatgpt_ans.append(f"\n\nUser: {question}")
            self.dlg.chatgpt_ans.append("\nProcessing with GeoGenie AI...")

            # Get model and API keys with safe access
            model = getattr(self.dlg, 'model', None)
            if model is None:
                self.dlg.chatgpt_ans.append("\n❌ Error: Model selection widget not found")
                self._enable_ui()
                return
            
            model = model.currentText() if model.currentText() else "gpt-3.5-turbo"
            
            temperature_widget = getattr(self.dlg, 'temperature', None)
            temperature = temperature_widget.value() if temperature_widget else 0.1
            
            openai_api_key = None
            claude_api_key = None
            
            if self.is_claude_model(model):
                # Get Claude API key
                claude_widget = getattr(self.dlg, 'claude_apikey', None)
                if claude_widget and claude_widget.text():
                    claude_api_key = claude_widget.text()
                    # Save key
                    with open(self.claude_api_key_path, 'w') as f:
                        f.write(claude_api_key)
                elif os.path.exists(self.claude_api_key_path):
                    with open(self.claude_api_key_path, 'r') as f:
                        claude_api_key = f.read().strip()
                else:
                    self.showMessage("GeoGenie", "Please enter your Claude API key.", "OK", "Warning")
                    self._enable_ui()
                    return
            else:
                # Get OpenAI API key
                openai_widget = getattr(self.dlg, 'custom_apikey', None)
                if openai_widget and openai_widget.text():
                    openai_api_key = openai_widget.text()
                    # Save key
                    with open(self.api_key_path, 'w') as f:
                        f.write(openai_api_key)
                elif os.path.exists(self.api_key_path):
                    with open(self.api_key_path, 'r') as f:
                        openai_api_key = f.read().strip()
                else:
                    self.showMessage("GeoGenie", "Please enter your OpenAI API key.", "OK", "Warning")
                    self._enable_ui()
                    return

            # Initialize coordinator if needed
            if not self.coordinator:
                self.dlg.chatgpt_ans.append("\n🔧 Initializing GeoGenie coordinator...")
                self.coordinator = GeoGenieCoordinator()
                # Connect signals
                self.coordinator.processing_completed.connect(self._on_processing_completed)
                self.coordinator.processing_error.connect(self._on_processing_error)

            # Initialize LLM client
            self.dlg.chatgpt_ans.append(f"\n🤖 Initializing LLM client with model: {model}")
            if not self.coordinator.initialize_llm_client(
                openai_api_key=openai_api_key,
                claude_api_key=claude_api_key,
                model=model
            ):
                self.showMessage("GeoGenie", "Failed to initialize LLM client. Check your API key.", "OK", "Warning")
                self._enable_ui()
                return

            # Process the request
            self.dlg.chatgpt_ans.append(f"\n🔍 Processing request: '{question}'")
            success = self.coordinator.process_natural_language_request(
                prompt=question,
                parent_widget=self.dlg
            )

            if not success:
                self.dlg.chatgpt_ans.append("\n❌ Failed to process request. Check QGIS message log for details.")
                self._enable_ui()

        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            QgsMessageLog.logMessage(error_msg, 'GeoGenie', Qgis.Critical)
            self.dlg.chatgpt_ans.append(f"\n❌ Error: {str(e)}")
            self._enable_ui()

    def _on_processing_completed(self, result):
        """Handle successful processing completion"""
        try:
            explanation = result.get('explanation', 'Processing completed successfully.')
            self.dlg.chatgpt_ans.append(f"\n✅ GeoGenie: {explanation}")
            
            # Add to history
            conversation_pair = f"{self.questions[-1]} {explanation}"
            self.history.append(conversation_pair)
            
            # Update edit area
            self.dlg.chatgpt_edit.setText(explanation)
            
            # Clear question
            self.dlg.question.setText('')
            
            # Scroll to bottom
            self.dlg.chatgpt_ans.verticalScrollBar().setValue(
                self.dlg.chatgpt_ans.verticalScrollBar().maximum()
            )
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error handling completion: {str(e)}", 'GeoGenie', Qgis.Warning)
        finally:
            self._enable_ui()

    def _on_processing_error(self, error_message):
        """Handle processing errors"""
        self.dlg.chatgpt_ans.append(f"\n❌ Error: {error_message}")
        self._enable_ui()

    def _disable_ui(self):
        """Disable UI during processing"""
        self.dlg.send_chat.setEnabled(False)
        self.dlg.question.setEnabled(False)

    def _enable_ui(self):
        """Enable UI after processing"""
        self.dlg.send_chat.setEnabled(True)
        self.dlg.question.setEnabled(True)

    def clear_ans_fun(self):
        """Clear chat history"""
        self.history = deque(maxlen=6)
        self.answers = ['Welcome to GeoGenie - Your AI-Powered Geospatial Assistant.\n\nPhase 1 Features:\n• Natural language QGIS processing\n• Buffer, clip, reproject, dissolve, intersection\n• Parameter validation and confirmation\n• Real-time progress feedback']
        self.dlg.chatgpt_ans.clear()
        self.dlg.chatgpt_ans.append(self.answers[0])

    def export_messages(self):
        """Export chat messages to file"""
        from qgis.PyQt.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getSaveFileName(
            self.dlg, 
            'Export GeoGenie Chat', 
            os.path.join(os.path.expanduser('~'), 'Desktop', 'geogenie_chat.txt'),
            'Text files (*.txt)'
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(self.dlg.chatgpt_ans.toPlainText())
                self.showMessage("GeoGenie", f"Chat exported to: {filename}", "OK", "Info")
            except Exception as e:
                self.showMessage("GeoGenie", f"Export failed: {str(e)}", "OK", "Warning")

    def read_api_keys(self):
        """Read saved API keys"""
        try:
            # Read OpenAI API key
            if os.path.exists(self.api_key_path):
                with open(self.api_key_path, 'r') as f:
                    key = f.read().strip()
                openai_widget = getattr(self.dlg, 'custom_apikey', None)
                if openai_widget:
                    openai_widget.setText(key)
            
            # Read Claude API key
            if os.path.exists(self.claude_api_key_path):
                with open(self.claude_api_key_path, 'r') as f:
                    key = f.read().strip()
                claude_widget = getattr(self.dlg, 'claude_apikey', None)
                if claude_widget:
                    claude_widget.setText(key)
        except Exception as e:
            QgsMessageLog.logMessage(f"Error reading API keys: {str(e)}", 'GeoGenie', Qgis.Warning)

    def command_history(self, up=False):
        """Navigate command history"""
        if self.questions:
            if up:
                self.questions_index = max(0, self.questions_index - 1)
                self.dlg.question.setText(self.questions[self.questions_index])
            else:
                self.questions_index = min(len(self.questions) - 1, self.questions_index + 1)
                self.dlg.question.setText(self.questions[self.questions_index])

    def run(self):
        """Run method that loads the plugin UI"""
        
        # Create the dialog with elements (after translation) and keep reference
        if self.first_start:
            self.first_start = False
            self.dlg = GeoGenieDockWidget()
            self.read_api_keys()

        # Initialize answers
        self.questions = []
        self.answers = ['Welcome to GeoGenie - Your AI-Powered Geospatial Assistant.\n\nPhase 1 Features:\n• Natural language QGIS processing\n• Buffer, clip, reproject, dissolve, intersection\n• Parameter validation and confirmation\n• Real-time progress feedback']

        # Show dockwidget at the bottom
        self.iface.addDockWidget(Qt.BottomDockWidgetArea, self.dlg)
        self.dlg.question.setFocus(True)

        # Connect signals
        self.dlg.send_chat.clicked.connect(self.send_message)
        self.dlg.question.returnPressed.connect(self.send_message)
        
        if hasattr(self.dlg, 'export_ans'):
            self.dlg.export_ans.clicked.connect(self.export_messages)
        if hasattr(self.dlg, 'clear_ans'):
            self.dlg.clear_ans.clicked.connect(self.clear_ans_fun)

        # Enable history navigation
        up_arrow = QShortcut(QKeySequence.MoveToNextLine, self.dlg.question)
        up_arrow.activated.connect(lambda: self.command_history(False))
        down_arrow = QShortcut(QKeySequence.MoveToPreviousLine, self.dlg.question)
        down_arrow.activated.connect(lambda: self.command_history(True))

        # Set default values
        if hasattr(self.dlg, 'temperature'):
            self.dlg.temperature.setValue(0.1)  # Lower temperature for more deterministic results
        if hasattr(self.dlg, 'max_tokens'):
            self.dlg.max_tokens.setValue(2000)

        # Initialize chat area
        self.dlg.chatgpt_ans.clear()
        self.dlg.chatgpt_ans.setAcceptRichText(True)
        self.dlg.chatgpt_ans.append(self.answers[0])
        
        QgsMessageLog.logMessage("GeoGenie plugin started", 'GeoGenie', Qgis.Info)
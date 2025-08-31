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

# Check API dependencies with detailed error reporting
API_EXIST = False
MISSING_PACKAGES = []

try:
    import openai
except ImportError as e:
    MISSING_PACKAGES.append(f"openai (error: {str(e)})")

try:
    import anthropic
except ImportError as e:
    MISSING_PACKAGES.append(f"anthropic (error: {str(e)})")

try:
    import google.generativeai
except ImportError as e:
    MISSING_PACKAGES.append(f"google-generativeai (error: {str(e)})")

try:
    import requests
except ImportError as e:
    MISSING_PACKAGES.append(f"requests (error: {str(e)})")

API_EXIST = len(MISSING_PACKAGES) == 0


class GeoGenie:
    """QGIS Plugin Implementation for GeoGenie Phase 1"""

    def __init__(self, iface):
        """Constructor"""
        self.iface = iface
        
        # Initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        self.api_key_path = os.path.join(self.plugin_dir, 'api_key.txt')
        self.claude_api_key_path = os.path.join(self.plugin_dir, 'claude_api_key.txt')
        self.gemini_api_key_path = os.path.join(self.plugin_dir, 'gemini_api_key.txt')
        self.ollama_url_path = os.path.join(self.plugin_dir, 'ollama_url.txt')
        
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
        
        # Debug: Log Python path and package availability
        import sys
        QgsMessageLog.logMessage(f"Python path: {sys.executable}", 'GeoGenie', Qgis.Info)
        QgsMessageLog.logMessage(f"API packages available: {API_EXIST}", 'GeoGenie', Qgis.Info)
        if MISSING_PACKAGES:
            QgsMessageLog.logMessage(f"Missing packages: {MISSING_PACKAGES}", 'GeoGenie', Qgis.Warning)

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

    def get_provider_models(self, provider):
        """Get available models for a provider"""
        models = {
            'openai': [
                'gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4',
                'gpt-3.5-turbo', 'gpt-3.5-turbo-16k'
            ],
            'anthropic': [
                'claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022',
                'claude-3-opus-20240229', 'claude-3-sonnet-20240229', 
                'claude-3-haiku-20240307'
            ],
            'gemini': [
                'gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.0-flash'
            ],
            'ollama': [
                'llama3.1', 'llama3.1:70b', 'llama3.1:8b',
                'codellama', 'mistral', 'qwen2.5:32b'
            ]
        }
        return models.get(provider, [])
    
    def update_model_list(self, provider):
        """Update model dropdown based on selected provider"""
        if hasattr(self.dlg, 'model'):
            self.dlg.model.clear()
            models = self.get_provider_models(provider)
            self.dlg.model.addItems(models)
            if models:
                self.dlg.model.setCurrentIndex(0)
    
    def test_dependencies(self):
        """Test and report package installation status"""
        import sys
        import subprocess
        
        report = ["=== GeoGenie Dependency Test ==="]
        report.append(f"Python executable: {sys.executable}")
        report.append(f"Python version: {sys.version}")
        report.append("")
        
        # Test each package individually
        for package_name in ['openai', 'anthropic', 'google-generativeai', 'requests']:
            try:
                if package_name == 'openai':
                    import openai
                    report.append(f"✅ {package_name}: {openai.__version__}")
                elif package_name == 'anthropic':
                    import anthropic
                    report.append(f"✅ {package_name}: {anthropic.__version__}")
                elif package_name == 'google-generativeai':
                    import google.generativeai
                    report.append(f"✅ {package_name}: Available")
                elif package_name == 'requests':
                    import requests
                    report.append(f"✅ {package_name}: {requests.__version__}")
            except ImportError as e:
                report.append(f"❌ {package_name}: {str(e)}")
                # Try to get more info
                try:
                    result = subprocess.run([sys.executable, '-m', 'pip', 'show', package_name], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        report.append(f"   Pip shows: {result.stdout.split('Version:')[1].split('\\n')[0].strip()}")
                    else:
                        report.append(f"   Not installed via pip")
                except Exception:
                    report.append(f"   Could not check pip status")
        
        report_text = "\n".join(report)
        QgsMessageLog.logMessage(report_text, 'GeoGenie', Qgis.Info)
        self.showMessage("GeoGenie Dependency Test", report_text, "OK", "Info")
        return report_text

    def create_spatial_indexes(self):
        """Create spatial indexes for all vector layers to improve performance"""
        try:
            from .context_manager import ContextManager
            
            # Show progress
            self.dlg.chatgpt_ans.append("\n🔧 Creating spatial indexes for all vector layers...")
            
            # Create context manager and run spatial indexing
            context_manager = ContextManager()
            results = context_manager.ensure_spatial_indexes()
            
            # Count results
            total_layers = len(results)
            successful = sum(1 for success in results.values() if success)
            failed = total_layers - successful
            
            # Report results
            if total_layers == 0:
                self.dlg.chatgpt_ans.append("ℹ️ No vector layers found in the project.")
            else:
                self.dlg.chatgpt_ans.append(f"\n✅ Spatial Index Creation Complete:")
                self.dlg.chatgpt_ans.append(f"   • Total layers processed: {total_layers}")
                self.dlg.chatgpt_ans.append(f"   • Successfully indexed: {successful}")
                if failed > 0:
                    self.dlg.chatgpt_ans.append(f"   • Failed: {failed}")
                
                self.dlg.chatgpt_ans.append(f"\n🚀 Performance should be improved for spatial operations!")
                
                # List layers with new indexes
                new_indexes = [name for name, success in results.items() if success]
                if new_indexes:
                    self.dlg.chatgpt_ans.append(f"\nLayers with spatial indexes:")
                    for layer_name in new_indexes[:5]:  # Show first 5
                        self.dlg.chatgpt_ans.append(f"   • {layer_name}")
                    if len(new_indexes) > 5:
                        self.dlg.chatgpt_ans.append(f"   • ... and {len(new_indexes)-5} more")
            
            # Scroll to bottom
            self.dlg.chatgpt_ans.verticalScrollBar().setValue(
                self.dlg.chatgpt_ans.verticalScrollBar().maximum()
            )
            
        except Exception as e:
            error_msg = f"Error creating spatial indexes: {str(e)}"
            QgsMessageLog.logMessage(error_msg, 'GeoGenie', Qgis.Critical)
            self.dlg.chatgpt_ans.append(f"\n❌ Error: {str(e)}")

    def send_message(self):
        """Process natural language message using GeoGenie Phase 1"""
        
        if not API_EXIST:
            if MISSING_PACKAGES:
                error_msg = "Missing required packages:\n\n" + "\n".join(MISSING_PACKAGES)
                error_msg += "\n\nPlease install using:\npip install openai>=1.0.0 anthropic>=0.18.0"
            else:
                error_msg = "Unable to import required packages: openai, anthropic\n\nPlease install using:\npip install openai>=1.0.0 anthropic>=0.18.0"
            self.showMessage("GeoGenie - Missing Dependencies", error_msg, "OK", "Warning")
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
            
            # Handle special commands
            if question == "!test":
                self.test_dependencies()
                self.dlg.question.setText('')
                self._enable_ui()
                return
            elif question == "!index" or question == "!spatial-index":
                self.create_spatial_indexes()
                self.dlg.question.setText('')
                self._enable_ui()
                return

            # Add to history
            self.questions.append(question)
            self.questions_index = len(self.questions)

            # Update chat display
            self.dlg.chatgpt_ans.append("-" * 130)
            self.dlg.chatgpt_ans.append( 
                f'<div style="text-align: right; margin: 10px; padding: 10px; '
                f'background-color: #adb8b4;">'
                f'<b>You:</b><br>{question}</div>')
            #self.dlg.chatgpt_ans.append("\nProcessing with GeoGenie AI...")

            # Get provider, model and API keys
            provider_widget = getattr(self.dlg, 'provider_combo', None)
            if provider_widget is None:
                self.dlg.chatgpt_ans.append("\n❌ Error: Provider selection widget not found")
                self._enable_ui()
                return
            
            provider_text = provider_widget.currentText()
            provider_map = {
                'OpenAI': 'openai',
                'Anthropic (Claude)': 'anthropic', 
                'Google (Gemini)': 'gemini',
                'Ollama (Local)': 'ollama'
            }
            provider = provider_map.get(provider_text, 'openai')
            
            model_widget = getattr(self.dlg, 'model', None)
            if model_widget is None:
                self.dlg.chatgpt_ans.append("\n❌ Error: Model selection widget not found")
                self._enable_ui()
                return
            
            model = model_widget.currentText() if model_widget.currentText() else self.get_provider_models(provider)[0]
            
            temperature_widget = getattr(self.dlg, 'temperature', None)
            temperature = temperature_widget.value() if temperature_widget else 0.1
            
            # Get API keys based on provider
            api_keys = {}
            
            if provider == 'openai':
                openai_widget = getattr(self.dlg, 'custom_apikey', None)
                if openai_widget and openai_widget.text():
                    api_keys['openai_api_key'] = openai_widget.text()
                    with open(self.api_key_path, 'w') as f:
                        f.write(api_keys['openai_api_key'])
                elif os.path.exists(self.api_key_path):
                    with open(self.api_key_path, 'r') as f:
                        api_keys['openai_api_key'] = f.read().strip()
                else:
                    self.showMessage("GeoGenie", "Please enter your OpenAI API key.", "OK", "Warning")
                    self._enable_ui()
                    return
                    
            elif provider == 'anthropic':
                claude_widget = getattr(self.dlg, 'claude_apikey', None)
                if claude_widget and claude_widget.text():
                    api_keys['anthropic_api_key'] = claude_widget.text()
                    with open(self.claude_api_key_path, 'w') as f:
                        f.write(api_keys['anthropic_api_key'])
                elif os.path.exists(self.claude_api_key_path):
                    with open(self.claude_api_key_path, 'r') as f:
                        api_keys['anthropic_api_key'] = f.read().strip()
                else:
                    self.showMessage("GeoGenie", "Please enter your Claude API key.", "OK", "Warning")
                    self._enable_ui()
                    return
                    
            elif provider == 'gemini':
                gemini_widget = getattr(self.dlg, 'gemini_apikey', None)
                if gemini_widget and gemini_widget.text():
                    api_keys['gemini_api_key'] = gemini_widget.text()
                    with open(self.gemini_api_key_path, 'w') as f:
                        f.write(api_keys['gemini_api_key'])
                elif os.path.exists(self.gemini_api_key_path):
                    with open(self.gemini_api_key_path, 'r') as f:
                        api_keys['gemini_api_key'] = f.read().strip()
                else:
                    self.showMessage("GeoGenie", "Please enter your Gemini API key.", "OK", "Warning")
                    self._enable_ui()
                    return
                    
            elif provider == 'ollama':
                ollama_widget = getattr(self.dlg, 'ollama_url', None)
                if ollama_widget and ollama_widget.text():
                    api_keys['ollama_url'] = ollama_widget.text()
                    with open(self.ollama_url_path, 'w') as f:
                        f.write(api_keys['ollama_url'])
                elif os.path.exists(self.ollama_url_path):
                    with open(self.ollama_url_path, 'r') as f:
                        api_keys['ollama_url'] = f.read().strip()
                else:
                    # Default Ollama URL
                    api_keys['ollama_url'] = 'http://localhost:11434'

            # Initialize coordinator if needed
            if not self.coordinator:
                #self.dlg.chatgpt_ans.append("\n🔧 Initializing GeoGenie coordinator...")
                self.coordinator = GeoGenieCoordinator()
                # Connect signals
                self.coordinator.processing_completed.connect(self._on_processing_completed)
                self.coordinator.processing_error.connect(self._on_processing_error)

            # Initialize LLM client with provider support
            #self.dlg.chatgpt_ans.append(f"\n🤖 Initializing {provider.title()} LLM client with model: {model}")
            if not self.coordinator.initialize_llm_client(
                provider=provider,
                model=model,
                **api_keys
            ):
                self.showMessage("GeoGenie", f"Failed to initialize {provider.title()} LLM client. Check your credentials.", "OK", "Warning")
                self._enable_ui()
                return

            # Process the request
            #self.dlg.chatgpt_ans.append(f"\n🔍 Processing request: '{question}'")
            success = self.coordinator.process_natural_language_request(
                prompt=question,
                parent_widget=self.dlg
            )

            if not success:
                self.dlg.chatgpt_ans.append("-" * 130)
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
            self.dlg.chatgpt_ans.append("-" * 130)
            self.dlg.chatgpt_ans.append( 
                f'<div style="text-align: left; margin: 10px; padding: 10px; '
                f'background-color: #adb8b4; margin-right: 5px;">'
                f'<b>GeoGenie:</b><br>{explanation}</div>')
            
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
        #self.answers = ['']
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
                    
            # Read Gemini API key
            if os.path.exists(self.gemini_api_key_path):
                with open(self.gemini_api_key_path, 'r') as f:
                    key = f.read().strip()
                gemini_widget = getattr(self.dlg, 'gemini_apikey', None)
                if gemini_widget:
                    gemini_widget.setText(key)
                    
            # Read Ollama URL
            if os.path.exists(self.ollama_url_path):
                with open(self.ollama_url_path, 'r') as f:
                    url = f.read().strip()
                ollama_widget = getattr(self.dlg, 'ollama_url', None)
                if ollama_widget:
                    ollama_widget.setText(url)
            else:
                # Set default Ollama URL
                ollama_widget = getattr(self.dlg, 'ollama_url', None)
                if ollama_widget:
                    ollama_widget.setText('http://localhost:11434')
                    
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
        #dependency_status = "✅ Dependencies OK" if API_EXIST else f"❌ Missing: {', '.join(MISSING_PACKAGES[:2])}"
        #self.answers = [f'Status: {dependency_status}\n\nType "!test" to run dependency diagnostics.']

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
            
        # Connect provider selection to model update
        if hasattr(self.dlg, 'provider_combo'):
            self.dlg.provider_combo.currentTextChanged.connect(
                lambda text: self.update_model_list({
                    'OpenAI': 'openai',
                    'Anthropic (Claude)': 'anthropic', 
                    'Google (Gemini)': 'gemini',
                    'Ollama (Local)': 'ollama'
                }.get(text, 'openai'))
            )
            # Initialize with default provider
            self.update_model_list('openai')

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

        # Initialize chat area with HTML 
        self.dlg.chatgpt_ans.clear()
        self.dlg.chatgpt_ans.setAcceptRichText(True)
        msg = ("Hi! I'm GeoGenie, How can I help you today?")
        self.dlg.chatgpt_ans.append(
            f'<div style="text-align: left; margin: 10px; padding: 10px; '
            f'background-color: #adb8b4; margin-right: 5px;">'
            f'<b>GeoGenie:</b><br>{msg}</div>')
        
        QgsMessageLog.logMessage("GeoGenie plugin started", 'GeoGenie', Qgis.Info)
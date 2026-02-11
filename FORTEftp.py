"""
FORTEftp - Profesionální FTP/SSH klient
Autor: FORTE
Verze: 1.0
"""

import sys
import json
import os
import subprocess
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QListWidget, QPushButton, QLabel,
    QLineEdit, QTabWidget, QSplitter, QMessageBox, QFileDialog,
    QDialog, QFormLayout, QComboBox, QSpinBox, QTextEdit, QMenu,
    QInputDialog, QProgressDialog, QCheckBox, QGroupBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QFont
import ftplib
from ftplib import FTP, FTP_TLS
import paramiko
from io import BytesIO
import stat

# Soubor pro ukládání prostředí
CONFIG_FILE = "forte_environments.json"


class EnvironmentDialog(QDialog):
    """Dialog pro vytvoření/editaci FTP/SSH prostředí"""
    
    def __init__(self, parent=None, env_data=None):
        super().__init__(parent)
        self.setWindowTitle("Nastavení prostředí")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        layout = QFormLayout()
        
        # Název prostředí
        self.name_input = QLineEdit()
        layout.addRow("Název prostředí:", self.name_input)
        
        # Typ připojení
        self.type_combo = QComboBox()
        self.type_combo.addItems(["FTP", "FTPS", "SFTP (SSH)"])
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        layout.addRow("Typ:", self.type_combo)
        
        # Server
        self.host_input = QLineEdit()
        layout.addRow("Server:", self.host_input)
        
        # Port
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(21)
        layout.addRow("Port:", self.port_input)
        
        # Uživatel
        self.user_input = QLineEdit()
        layout.addRow("Uživatel:", self.user_input)
        
        # Heslo
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.Password)
        layout.addRow("Heslo:", self.pass_input)
        
        # Výchozí složka
        self.remote_path_input = QLineEdit()
        self.remote_path_input.setText("/")
        layout.addRow("Výchozí složka:", self.remote_path_input)
        
        # Tlačítka
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Uložit")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Zrušit")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addRow(btn_layout)
        self.setLayout(layout)
        
        # Načíst data pokud editujeme
        if env_data:
            self.load_data(env_data)
    
    def on_type_changed(self, index):
        """Změna výchozího portu podle typu"""
        if index == 0:  # FTP
            self.port_input.setValue(21)
        elif index == 1:  # FTPS
            self.port_input.setValue(990)
        elif index == 2:  # SFTP
            self.port_input.setValue(22)
    
    def load_data(self, data):
        """Načíst data do formuláře"""
        self.name_input.setText(data.get('name', ''))
        conn_type = data.get('type', 'FTP')
        index = self.type_combo.findText(conn_type)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)
        self.host_input.setText(data.get('host', ''))
        self.port_input.setValue(data.get('port', 21))
        self.user_input.setText(data.get('user', ''))
        self.pass_input.setText(data.get('password', ''))
        self.remote_path_input.setText(data.get('remote_path', '/'))
    
    def get_data(self):
        """Získat data z formuláře"""
        return {
            'name': self.name_input.text(),
            'type': self.type_combo.currentText(),
            'host': self.host_input.text(),
            'port': self.port_input.value(),
            'user': self.user_input.text(),
            'password': self.pass_input.text(),
            'remote_path': self.remote_path_input.text()
        }


class SSHTerminal(QWidget):
    """Widget pro SSH terminál"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ssh_client = None
        self.channel = None
        
        layout = QVBoxLayout()
        
        # Terminálový výstup
        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
            }
        """)
        layout.addWidget(self.terminal_output)
        
        # Vstupní pole pro příkazy
        cmd_layout = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Zadejte příkaz...")
        self.command_input.returnPressed.connect(self.execute_command)
        self.send_btn = QPushButton("Odeslat")
        self.send_btn.clicked.connect(self.execute_command)
        cmd_layout.addWidget(self.command_input)
        cmd_layout.addWidget(self.send_btn)
        layout.addLayout(cmd_layout)
        
        self.setLayout(layout)
    
    def connect(self, host, port, username, password):
        """Připojení k SSH serveru"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(host, port=port, username=username, password=password)
            
            self.channel = self.ssh_client.invoke_shell()
            self.terminal_output.append(f"Připojeno k {host}:{port}\n")
            
            # Přečíst uvítací zprávu
            import time
            time.sleep(0.5)
            if self.channel.recv_ready():
                output = self.channel.recv(4096).decode('utf-8', errors='ignore')
                self.terminal_output.append(output)
            
            return True
        except Exception as e:
            QMessageBox.critical(self, "Chyba SSH", f"Nepodařilo se připojit:\n{str(e)}")
            return False
    
    def execute_command(self):
        """Vykonat příkaz"""
        if not self.channel:
            QMessageBox.warning(self, "SSH Terminal", "Nejste připojeni k SSH serveru!")
            return
        
        command = self.command_input.text()
        if not command:
            return
        
        try:
            self.terminal_output.append(f"$ {command}\n")
            self.channel.send(command + '\n')
            
            # Počkat na odpověď
            import time
            time.sleep(0.3)
            
            output = ""
            while self.channel.recv_ready():
                output += self.channel.recv(4096).decode('utf-8', errors='ignore')
            
            if output:
                self.terminal_output.append(output)
            
            self.command_input.clear()
            
        except Exception as e:
            self.terminal_output.append(f"Chyba: {str(e)}\n")
    
    def disconnect(self):
        """Odpojit SSH"""
        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None
            self.channel = None
            self.terminal_output.append("\nOdpojeno.\n")


class FileTransferThread(QThread):
    """Vlákno pro přenos souborů"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, operation, source, dest, ftp_client=None, ssh_client=None):
        super().__init__()
        self.operation = operation
        self.source = source
        self.dest = dest
        self.ftp_client = ftp_client
        self.ssh_client = ssh_client
    
    def run(self):
        try:
            if self.operation == "upload":
                self.upload_file()
            elif self.operation == "download":
                self.download_file()
            self.finished.emit(True, "Úspěšně dokončeno")
        except Exception as e:
            self.finished.emit(False, str(e))
    
    def upload_file(self):
        """Nahrát soubor na FTP"""
        with open(self.source, 'rb') as f:
            self.ftp_client.storbinary(f'STOR {self.dest}', f)
    
    def download_file(self):
        """Stáhnout soubor z FTP"""
        with open(self.dest, 'wb') as f:
            self.ftp_client.retrbinary(f'RETR {self.source}', f.write)


class FORTEftp(QMainWindow):
    """Hlavní okno aplikace FORTEftp"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FORTEftp - FTP/SSH Klient")
        self.setGeometry(100, 100, 1200, 700)
        
        # Nastavit ikonu
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.ftp_client = None
        self.ssh_client = None
        self.sftp_client = None
        self.current_env = None
        self.current_remote_path = "/"
        self.current_local_path = str(Path.home())
        self.git_repo_root = None
        
        self.init_ui()
        self.load_environments()
    
    def init_ui(self):
        """Inicializace uživatelského rozhraní"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        
        # Horní panel - výběr prostředí
        top_panel = self.create_top_panel()
        main_layout.addLayout(top_panel)
        
        # Hlavní obsah - záložky
        self.tabs = QTabWidget()
        
        # Záložka FTP správce
        self.ftp_tab = self.create_ftp_tab()
        self.tabs.addTab(self.ftp_tab, "📁 FTP Správce")
        
        # Záložka SSH terminál
        self.ssh_terminal = SSHTerminal()
        self.tabs.addTab(self.ssh_terminal, "💻 SSH Terminál")

        # Záložka Git
        self.git_tab = self.create_git_tab()
        self.tabs.addTab(self.git_tab, "🧩 Git")
        
        main_layout.addWidget(self.tabs)
        
        # Stavový řádek
        self.status_label = QLabel("Nepřipojeno")
        main_layout.addWidget(self.status_label)
        
        central_widget.setLayout(main_layout)
    
    def create_top_panel(self):
        """Vytvořit horní panel s ovládáním"""
        layout = QHBoxLayout()
        
        # Výběr prostředí
        layout.addWidget(QLabel("Prostředí:"))
        self.env_combo = QComboBox()
        self.env_combo.setMinimumWidth(200)
        layout.addWidget(self.env_combo)
        
        # Tlačítka pro správu prostředí
        self.new_env_btn = QPushButton("➕ Nové")
        self.new_env_btn.clicked.connect(self.new_environment)
        layout.addWidget(self.new_env_btn)
        
        self.edit_env_btn = QPushButton("✏️ Upravit")
        self.edit_env_btn.clicked.connect(self.edit_environment)
        layout.addWidget(self.edit_env_btn)
        
        self.delete_env_btn = QPushButton("🗑️ Smazat")
        self.delete_env_btn.clicked.connect(self.delete_environment)
        layout.addWidget(self.delete_env_btn)
        
        layout.addSpacing(20)
        
        # Tlačítko připojit/odpojit
        self.connect_btn = QPushButton("🔌 Připojit")
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.connect_btn.setStyleSheet("QPushButton { font-weight: bold; padding: 5px 15px; }")
        layout.addWidget(self.connect_btn)
        
        layout.addStretch()
        
        return layout
    
    def create_ftp_tab(self):
        """Vytvořit záložku FTP správce"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Splitter pro rozdělení na levou a pravou část
        splitter = QSplitter(Qt.Horizontal)
        
        # Levá strana - lokální soubory
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        
        left_layout.addWidget(QLabel("💻 Lokální soubory:"))
        
        # Navigace
        local_nav = QHBoxLayout()
        self.local_path_input = QLineEdit(self.current_local_path)
        self.local_path_input.returnPressed.connect(self.refresh_local_files)
        local_nav.addWidget(self.local_path_input)
        self.local_refresh_btn = QPushButton("🔄")
        self.local_refresh_btn.clicked.connect(self.refresh_local_files)
        local_nav.addWidget(self.local_refresh_btn)
        left_layout.addLayout(local_nav)
        
        # Seznam souborů
        self.local_tree = QTreeWidget()
        self.local_tree.setHeaderLabels(["Název", "Velikost", "Typ"])
        self.local_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.local_tree.customContextMenuRequested.connect(self.local_context_menu)
        self.local_tree.itemDoubleClicked.connect(self.local_item_double_clicked)
        left_layout.addWidget(self.local_tree)
        
        left_panel.setLayout(left_layout)
        splitter.addWidget(left_panel)
        
        # Pravá strana - vzdálené soubory (FTP)
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        
        right_layout.addWidget(QLabel("🌐 Vzdálené soubory (FTP):"))
        
        # Navigace
        remote_nav = QHBoxLayout()
        self.remote_path_input = QLineEdit(self.current_remote_path)
        self.remote_path_input.returnPressed.connect(self.refresh_remote_files)
        remote_nav.addWidget(self.remote_path_input)
        self.remote_refresh_btn = QPushButton("🔄")
        self.remote_refresh_btn.clicked.connect(self.refresh_remote_files)
        remote_nav.addWidget(self.remote_refresh_btn)
        right_layout.addLayout(remote_nav)
        
        # Seznam souborů
        self.remote_tree = QTreeWidget()
        self.remote_tree.setHeaderLabels(["Název", "Velikost", "Typ"])
        self.remote_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.remote_tree.customContextMenuRequested.connect(self.remote_context_menu)
        self.remote_tree.itemDoubleClicked.connect(self.remote_item_double_clicked)
        right_layout.addWidget(self.remote_tree)
        
        right_panel.setLayout(right_layout)
        splitter.addWidget(right_panel)
        
        layout.addWidget(splitter)
        
        # Tlačítka pro přenos
        transfer_layout = QHBoxLayout()
        self.upload_btn = QPushButton("⬆️ Nahrát na server")
        self.upload_btn.clicked.connect(self.upload_file)
        self.upload_btn.setEnabled(False)
        transfer_layout.addWidget(self.upload_btn)
        
        self.download_btn = QPushButton("⬇️ Stáhnout ze serveru")
        self.download_btn.clicked.connect(self.download_file)
        self.download_btn.setEnabled(False)
        transfer_layout.addWidget(self.download_btn)
        
        self.upload_changes_btn = QPushButton("📤 Nahrát změny")
        self.upload_changes_btn.clicked.connect(self.upload_modified_files)
        self.upload_changes_btn.setEnabled(False)
        self.upload_changes_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        transfer_layout.addWidget(self.upload_changes_btn)
        
        layout.addLayout(transfer_layout)
        
        widget.setLayout(layout)
        
        # Načíst lokální soubory
        self.refresh_local_files()
        
        return widget

    def create_git_tab(self):
        """Vytvořit záložku Git"""
        widget = QWidget()
        layout = QVBoxLayout()

        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Hledat v:"))
        self.git_repo_path_input = QLineEdit(self.current_local_path)
        search_layout.addWidget(self.git_repo_path_input)
        self.git_browse_repo_btn = QPushButton("📂 Vybrat složku")
        self.git_browse_repo_btn.clicked.connect(self.select_git_folder)
        search_layout.addWidget(self.git_browse_repo_btn)
        layout.addLayout(search_layout)

        repo_layout = QHBoxLayout()
        repo_layout.addWidget(QLabel("Repo:"))
        self.git_repo_label = QLabel("(nenalezeno)")
        self.git_repo_label.setStyleSheet("font-weight: bold;")
        repo_layout.addWidget(self.git_repo_label)
        repo_layout.addStretch()
        self.git_detect_btn = QPushButton("🔍 Najít repo")
        self.git_detect_btn.clicked.connect(self.refresh_git_repo)
        repo_layout.addWidget(self.git_detect_btn)
        layout.addLayout(repo_layout)

        actions_layout = QHBoxLayout()
        self.git_status_btn = QPushButton("🔄 Status")
        self.git_status_btn.clicked.connect(self.refresh_git_status)
        actions_layout.addWidget(self.git_status_btn)

        self.git_fetch_btn = QPushButton("⬇️ Fetch")
        self.git_fetch_btn.clicked.connect(self.git_fetch)
        actions_layout.addWidget(self.git_fetch_btn)

        self.git_pull_btn = QPushButton("⬇️ Pull")
        self.git_pull_btn.clicked.connect(self.git_pull)
        actions_layout.addWidget(self.git_pull_btn)

        self.git_push_btn = QPushButton("⬆️ Push")
        self.git_push_btn.clicked.connect(self.git_push)
        actions_layout.addWidget(self.git_push_btn)

        self.git_diff_btn = QPushButton("🧾 Diff")
        self.git_diff_btn.clicked.connect(self.git_show_diff)
        actions_layout.addWidget(self.git_diff_btn)

        self.git_log_btn = QPushButton("📜 Log")
        self.git_log_btn.clicked.connect(self.git_show_log)
        actions_layout.addWidget(self.git_log_btn)

        actions_layout.addStretch()
        layout.addLayout(actions_layout)

        commit_layout = QHBoxLayout()
        self.git_commit_message = QLineEdit()
        self.git_commit_message.setPlaceholderText("Zadejte commit message...")
        commit_layout.addWidget(self.git_commit_message)
        self.git_commit_btn = QPushButton("✅ Commit")
        self.git_commit_btn.clicked.connect(self.git_commit)
        commit_layout.addWidget(self.git_commit_btn)
        layout.addLayout(commit_layout)

        branch_layout = QHBoxLayout()
        self.git_new_branch_input = QLineEdit()
        self.git_new_branch_input.setPlaceholderText("Nová branch...")
        branch_layout.addWidget(self.git_new_branch_input)
        self.git_create_branch_btn = QPushButton("➕ Vytvořit")
        self.git_create_branch_btn.clicked.connect(self.git_create_branch)
        branch_layout.addWidget(self.git_create_branch_btn)

        self.git_branch_combo = QComboBox()
        branch_layout.addWidget(self.git_branch_combo)
        self.git_switch_branch_btn = QPushButton("🔀 Přepnout")
        self.git_switch_branch_btn.clicked.connect(self.git_switch_branch)
        branch_layout.addWidget(self.git_switch_branch_btn)
        layout.addLayout(branch_layout)

        commands_group = QGroupBox("Rychlé příkazy")
        commands_layout = QVBoxLayout()
        self.git_quick_buttons = []

        def add_quick_command(text, args, description, requires_confirm=False, confirm_text=None):
            row_layout = QHBoxLayout()
            btn = QPushButton(text)
            btn.clicked.connect(
                lambda _, a=args, d=description, c=requires_confirm, t=confirm_text: self.git_quick_command(a, d, c, t)
            )
            desc = QLabel(description)
            desc.setWordWrap(True)
            row_layout.addWidget(btn)
            row_layout.addWidget(desc, 1)
            commands_layout.addLayout(row_layout)
            self.git_quick_buttons.append(btn)

        add_quick_command(
            "➕ Add .",
            ["add", "."],
            "Zastageuje nové a změněné soubory v aktuální složce."
        )
        add_quick_command(
            "➕ Add -u",
            ["add", "-u"],
            "Zastageuje úpravy a smazání již sledovaných souborů (nové nepřidá)."
        )
        add_quick_command(
            "➕ Add -A",
            ["add", "-A"],
            "Zastageuje všechny změny v repo (nové, úpravy i smazání)."
        )
        add_quick_command(
            "↩️ Restore --staged .",
            ["restore", "--staged", "."],
            "Odstageuje změny, ale ponechá je v working tree."
        )
        add_quick_command(
            "↩️ Restore .",
            ["restore", "."],
            "Zahodí změny v working tree pro aktuální složku.",
            True,
            "Tento příkaz zahodí lokální změny. Pokračovat?"
        )
        add_quick_command(
            "🧹 Reset --soft HEAD~1",
            ["reset", "--soft", "HEAD~1"],
            "Zruší poslední commit, změny zůstanou staged."
        )
        add_quick_command(
            "🧹 Reset --mixed HEAD~1",
            ["reset", "--mixed", "HEAD~1"],
            "Zruší poslední commit, změny zůstanou v working tree (unstaged)."
        )
        add_quick_command(
            "☠️ Reset --hard HEAD~1",
            ["reset", "--hard", "HEAD~1"],
            "Zruší poslední commit a zahodí změny (nevratné).",
            True,
            "Tento příkaz je nevratný a zahodí změny. Pokračovat?"
        )
        add_quick_command(
            "📦 Stash",
            ["stash"],
            "Uloží rozpracované změny do stash a vyčistí working tree."
        )
        add_quick_command(
            "📦 Stash pop",
            ["stash", "pop"],
            "Obnoví poslední stash a odstraní ho ze zásobníku."
        )
        add_quick_command(
            "⬆️ Push --force",
            ["push", "--force"],
            "Vynutí přepsání historie na remote (rizikové).",
            True,
            "Force push může přepsat historii na remote. Pokračovat?"
        )
        add_quick_command(
            "⬆️ Push --force-with-lease",
            ["push", "--force-with-lease"],
            "Bezpečnější force push, selže pokud na remote přibyly změny.",
            True,
            "Force-with-lease může přepsat historii na remote. Pokračovat?"
        )

        commands_group.setLayout(commands_layout)
        layout.addWidget(commands_group)

        self.git_outputs = QTabWidget()
        self.git_status_output = QTextEdit()
        self.git_status_output.setReadOnly(True)
        self.git_outputs.addTab(self.git_status_output, "Status")

        self.git_diff_output = QTextEdit()
        self.git_diff_output.setReadOnly(True)
        self.git_outputs.addTab(self.git_diff_output, "Diff")

        self.git_log_output = QTextEdit()
        self.git_log_output.setReadOnly(True)
        self.git_outputs.addTab(self.git_log_output, "Log")

        layout.addWidget(self.git_outputs)

        widget.setLayout(layout)
        self.set_git_ui_enabled(False)
        self.refresh_git_repo()
        return widget
    
    def load_environments(self):
        """Načíst uložená prostředí"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self.environments = json.load(f)
            except:
                self.environments = []
        else:
            self.environments = []
        
        self.update_env_combo()
    
    def save_environments(self):
        """Uložit prostředí"""
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.environments, f, indent=2, ensure_ascii=False)
    
    def update_env_combo(self):
        """Aktualizovat seznam prostředí"""
        self.env_combo.clear()
        for env in self.environments:
            self.env_combo.addItem(env['name'])
    
    def new_environment(self):
        """Vytvořit nové prostředí"""
        dialog = EnvironmentDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data['name']:
                self.environments.append(data)
                self.save_environments()
                self.update_env_combo()
                self.env_combo.setCurrentText(data['name'])
    
    def edit_environment(self):
        """Upravit prostředí"""
        current_name = self.env_combo.currentText()
        if not current_name:
            return
        
        env = next((e for e in self.environments if e['name'] == current_name), None)
        if env:
            dialog = EnvironmentDialog(self, env)
            if dialog.exec_() == QDialog.Accepted:
                data = dialog.get_data()
                env.update(data)
                self.save_environments()
                self.update_env_combo()
                self.env_combo.setCurrentText(data['name'])
    
    def delete_environment(self):
        """Smazat prostředí"""
        current_name = self.env_combo.currentText()
        if not current_name:
            return
        
        reply = QMessageBox.question(
            self, 
            "Potvrzení",
            f"Opravdu chcete smazat prostředí '{current_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.environments = [e for e in self.environments if e['name'] != current_name]
            self.save_environments()
            self.update_env_combo()
    
    def toggle_connection(self):
        """Připojit/Odpojit"""
        if self.ftp_client or self.ssh_client:
            self.disconnect()
        else:
            self.connect()
    
    def connect(self):
        """Připojit k serveru"""
        current_name = self.env_combo.currentText()
        if not current_name:
            QMessageBox.warning(self, "FORTEftp", "Vyberte prostředí!")
            return
        
        env = next((e for e in self.environments if e['name'] == current_name), None)
        if not env:
            return
        
        self.current_env = env
        conn_type = env['type']
        
        try:
            if conn_type in ["FTP", "FTPS"]:
                # FTP připojení
                if conn_type == "FTPS":
                    self.ftp_client = FTP_TLS()
                else:
                    self.ftp_client = FTP()
                
                self.ftp_client.connect(env['host'], env['port'])
                self.ftp_client.login(env['user'], env['password'])
                
                if conn_type == "FTPS":
                    self.ftp_client.prot_p()
                
                self.current_remote_path = env.get('remote_path', '/')
                self.ftp_client.cwd(self.current_remote_path)
                
                self.status_label.setText(f"✅ Připojeno k {env['host']} (FTP)")
                self.connect_btn.setText("🔌 Odpojit")
                self.upload_btn.setEnabled(True)
                self.download_btn.setEnabled(True)
                self.upload_changes_btn.setEnabled(True)
                
                self.refresh_remote_files()
                
            elif conn_type == "SFTP (SSH)":
                # SSH připojení
                success = self.ssh_terminal.connect(
                    env['host'], 
                    env['port'], 
                    env['user'], 
                    env['password']
                )
                
                if success:
                    # Pro SFTP také připojit SSH klienta pro přenos souborů
                    self.ssh_client = paramiko.SSHClient()
                    self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    self.ssh_client.connect(
                        env['host'], 
                        port=env['port'], 
                        username=env['user'], 
                        password=env['password']
                    )
                    self.sftp_client = self.ssh_client.open_sftp()
                    
                    self.current_remote_path = env.get('remote_path', '/')
                    
                    self.status_label.setText(f"✅ Připojeno k {env['host']} (SSH/SFTP)")
                    self.connect_btn.setText("🔌 Odpojit")
                    self.upload_btn.setEnabled(True)
                    self.download_btn.setEnabled(True)
                    self.upload_changes_btn.setEnabled(True)
                    
                    self.refresh_remote_files()
                    self.tabs.setCurrentWidget(self.ssh_terminal)
        
        except Exception as e:
            QMessageBox.critical(self, "Chyba připojení", f"Nepodařilo se připojit:\n{str(e)}")
            self.disconnect()
    
    def disconnect(self):
        """Odpojit od serveru"""
        if self.ftp_client:
            try:
                self.ftp_client.quit()
            except:
                pass
            self.ftp_client = None
        
        if self.ssh_client:
            try:
                self.sftp_client.close()
                self.ssh_client.close()
            except:
                pass
            self.ssh_client = None
            self.sftp_client = None
        
        self.ssh_terminal.disconnect()
        
        self.status_label.setText("Odpojeno")
        self.connect_btn.setText("🔌 Připojit")
        self.upload_btn.setEnabled(False)
        self.upload_changes_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.remote_tree.clear()
    
    def refresh_local_files(self):
        """Obnovit seznam lokálních souborů"""
        path = self.local_path_input.text()
        if not os.path.exists(path):
            return
        
        self.current_local_path = path
        self.local_tree.clear()

        if hasattr(self, "git_repo_label"):
            self.git_repo_path_input.setText(self.current_local_path)
            self.refresh_git_repo()
        
        try:
            # Přidat odkaz na nadřazenou složku
            if path != "/":
                parent_item = QTreeWidgetItem(self.local_tree)
                parent_item.setText(0, "..")
                parent_item.setText(2, "📁 Složka")
                parent_item.setData(0, Qt.UserRole, str(Path(path).parent))
            
            # Načíst obsah složky
            for item in sorted(Path(path).iterdir(), key=lambda x: (not x.is_dir(), x.name)):
                tree_item = QTreeWidgetItem(self.local_tree)
                tree_item.setText(0, item.name)
                tree_item.setData(0, Qt.UserRole, str(item))
                
                if item.is_dir():
                    tree_item.setText(2, "📁 Složka")
                else:
                    size = item.stat().st_size
                    tree_item.setText(1, self.format_size(size))
                    tree_item.setText(2, "📄 Soubor")
        
        except Exception as e:
            QMessageBox.warning(self, "Chyba", f"Nelze načíst složku:\n{str(e)}")

    def set_git_ui_enabled(self, enabled):
        """Povolit/zakázat Git ovládací prvky"""
        self.git_status_btn.setEnabled(enabled)
        self.git_fetch_btn.setEnabled(enabled)
        self.git_pull_btn.setEnabled(enabled)
        self.git_push_btn.setEnabled(enabled)
        self.git_diff_btn.setEnabled(enabled)
        self.git_log_btn.setEnabled(enabled)
        self.git_commit_btn.setEnabled(enabled)
        self.git_commit_message.setEnabled(enabled)
        self.git_new_branch_input.setEnabled(enabled)
        self.git_create_branch_btn.setEnabled(enabled)
        self.git_branch_combo.setEnabled(enabled)
        self.git_switch_branch_btn.setEnabled(enabled)
        for btn in getattr(self, "git_quick_buttons", []):
            btn.setEnabled(enabled)

    def resolve_git_repo_root(self, path):
        """Najít Git repo root podle cesty"""
        try:
            result = subprocess.run(
                ["git", "-C", path, "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except Exception:
            return self.find_git_root_by_fs(path)

    def find_git_root_by_fs(self, path):
        """Najít Git repo root podle .git složky"""
        try:
            current = Path(path).resolve()
        except Exception:
            return None

        while True:
            if (current / ".git").is_dir():
                return str(current)
            if current.parent == current:
                break
            current = current.parent

        return None

    def run_git_command(self, args, repo_root=None):
        """Spustit Git příkaz v repo rootu"""
        root = repo_root or self.git_repo_root
        if not root:
            raise RuntimeError("Git repozitář nebyl nalezen.")

        try:
            result = subprocess.run(
                ["git", "-C", root] + args,
                capture_output=True,
                text=True
            )
        except FileNotFoundError:
            raise RuntimeError("Git není nainstalovaný nebo není v PATH.")

        output = result.stdout.strip()
        error = result.stderr.strip()

        if result.returncode != 0:
            raise RuntimeError(error or output or "Neznámá Git chyba.")

        return output

    def git_quick_command(self, args, description, requires_confirm=False, confirm_text=None):
        """Spustit rychlý Git příkaz s volitelným potvrzením"""
        if requires_confirm:
            reply = QMessageBox.question(
                self,
                "Git",
                confirm_text or "Tento příkaz může být nevratný. Pokračovat?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        try:
            output = self.run_git_command(args)
            if not output:
                output = f"Hotovo: {' '.join(['git'] + args)}"
            self.git_status_output.setPlainText(output)
            self.refresh_git_status()
        except Exception as e:
            QMessageBox.warning(self, "Git", str(e))

    def is_git_available(self):
        """Ověřit dostupnost git v PATH"""
        try:
            subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            return True
        except Exception:
            return False

    def refresh_git_repo(self):
        """Načíst Git repo dle zvolené složky"""
        search_path = self.git_repo_path_input.text().strip() or self.current_local_path
        repo_root = self.resolve_git_repo_root(search_path)
        self.git_repo_root = repo_root

        if repo_root:
            self.git_repo_label.setText(repo_root)
            if self.is_git_available():
                self.set_git_ui_enabled(True)
                self.refresh_git_status()
                self.git_load_branches()
            else:
                self.set_git_ui_enabled(False)
                self.git_status_output.setPlainText("Git nebyl nalezen v PATH. Nainstalujte Git a restartujte aplikaci.")
                self.git_diff_output.clear()
                self.git_log_output.clear()
                self.git_branch_combo.clear()
        else:
            self.git_repo_label.setText("(nenalezeno)")
            self.set_git_ui_enabled(False)
            self.git_status_output.setPlainText("Git repo nebyl nalezen v aktuální složce.")
            self.git_diff_output.clear()
            self.git_log_output.clear()
            self.git_branch_combo.clear()

    def select_git_folder(self):
        """Vybrat složku pro hledání Git repozitáře"""
        start_path = self.git_repo_path_input.text().strip() or self.current_local_path
        selected = QFileDialog.getExistingDirectory(
            self,
            "Vyberte složku s Git repozitářem",
            start_path
        )
        if selected:
            self.git_repo_path_input.setText(selected)
            self.refresh_git_repo()

    def refresh_git_status(self):
        """Načíst git status"""
        try:
            output = self.run_git_command(["status", "-sb"]) or "Čistý stav."
            self.git_status_output.setPlainText(output)
        except Exception as e:
            self.git_status_output.setPlainText(str(e))

    def git_fetch(self):
        """Fetch vzdálených změn"""
        try:
            output = self.run_git_command(["fetch", "--all"]) or "Fetch dokončen."
            self.git_status_output.setPlainText(output)
            self.refresh_git_status()
        except Exception as e:
            QMessageBox.warning(self, "Git", str(e))

    def git_pull(self):
        """Pull změn"""
        try:
            output = self.run_git_command(["pull"]) or "Pull dokončen."
            self.git_status_output.setPlainText(output)
            self.refresh_git_status()
        except Exception as e:
            QMessageBox.warning(self, "Git", str(e))

    def git_push(self):
        """Push změn"""
        try:
            output = self.run_git_command(["push"]) or "Push dokončen."
            self.git_status_output.setPlainText(output)
            self.refresh_git_status()
        except Exception as e:
            QMessageBox.warning(self, "Git", str(e))

    def git_commit(self):
        """Commit změn (git add -A + commit)"""
        message = self.git_commit_message.text().strip()
        if not message:
            QMessageBox.warning(self, "Git", "Zadejte commit message.")
            return

        try:
            self.run_git_command(["add", "-A"])
            output = self.run_git_command(["commit", "-m", message])
            self.git_commit_message.clear()
            self.git_status_output.setPlainText(output)
            self.refresh_git_status()
        except Exception as e:
            QMessageBox.warning(self, "Git", str(e))

    def git_create_branch(self):
        """Vytvořit novou branch"""
        branch_name = self.git_new_branch_input.text().strip()
        if not branch_name:
            QMessageBox.warning(self, "Git", "Zadejte název nové branche.")
            return

        try:
            output = self.run_git_command(["checkout", "-b", branch_name])
            self.git_new_branch_input.clear()
            self.git_status_output.setPlainText(output)
            self.git_load_branches()
            self.refresh_git_status()
        except Exception as e:
            QMessageBox.warning(self, "Git", str(e))

    def git_load_branches(self):
        """Načíst seznam branchí"""
        try:
            output = self.run_git_command(["branch", "--list"])
        except Exception as e:
            self.git_branch_combo.clear()
            self.git_status_output.setPlainText(str(e))
            return

        branches = []
        current_branch = None
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("*"):
                branch = line[1:].strip()
                current_branch = branch
            else:
                branch = line
            branches.append(branch)

        self.git_branch_combo.blockSignals(True)
        self.git_branch_combo.clear()
        self.git_branch_combo.addItems(branches)
        if current_branch:
            index = self.git_branch_combo.findText(current_branch)
            if index >= 0:
                self.git_branch_combo.setCurrentIndex(index)
        self.git_branch_combo.blockSignals(False)

    def git_switch_branch(self):
        """Přepnout branch"""
        branch = self.git_branch_combo.currentText().strip()
        if not branch:
            QMessageBox.warning(self, "Git", "Vyberte branch.")
            return

        try:
            output = self.run_git_command(["checkout", branch])
            self.git_status_output.setPlainText(output)
            self.refresh_git_status()
        except Exception as e:
            QMessageBox.warning(self, "Git", str(e))

    def git_show_log(self):
        """Zobrazit git log"""
        try:
            output = self.run_git_command(["log", "--oneline", "-n", "50"])
            self.git_log_output.setPlainText(output or "Bez záznamu.")
            self.git_outputs.setCurrentWidget(self.git_log_output)
        except Exception as e:
            self.git_log_output.setPlainText(str(e))

    def git_show_diff(self):
        """Zobrazit git diff"""
        try:
            output = self.run_git_command(["diff"])
            self.git_diff_output.setPlainText(output or "Žádné rozdíly.")
            self.git_outputs.setCurrentWidget(self.git_diff_output)
        except Exception as e:
            self.git_diff_output.setPlainText(str(e))
    
    def refresh_remote_files(self):
        """Obnovit seznam vzdálených souborů"""
        if not self.ftp_client and not self.sftp_client:
            return
        
        path = self.remote_path_input.text()
        self.current_remote_path = path
        self.remote_tree.clear()
        
        try:
            if self.ftp_client:
                # FTP
                self.ftp_client.cwd(path)
                
                # Přidat odkaz na nadřazenou složku
                if path != "/":
                    parent_item = QTreeWidgetItem(self.remote_tree)
                    parent_item.setText(0, "..")
                    parent_item.setText(2, "📁 Složka")
                    parent_path = "/".join(path.rstrip("/").split("/")[:-1])
                    if not parent_path:
                        parent_path = "/"
                    parent_item.setData(0, Qt.UserRole, parent_path)
                
                # Načíst obsah
                files = []
                self.ftp_client.dir(files.append)
                
                for file_info in files:
                    parts = file_info.split()
                    if len(parts) < 9:
                        continue
                    
                    name = " ".join(parts[8:])
                    if name in ['.', '..']:
                        continue
                    
                    tree_item = QTreeWidgetItem(self.remote_tree)
                    tree_item.setText(0, name)
                    tree_item.setData(0, Qt.UserRole, f"{path.rstrip('/')}/{name}")
                    
                    if file_info.startswith('d'):
                        tree_item.setText(2, "📁 Složka")
                    else:
                        try:
                            size = int(parts[4])
                            tree_item.setText(1, self.format_size(size))
                        except:
                            pass
                        tree_item.setText(2, "📄 Soubor")
            
            elif self.sftp_client:
                # SFTP
                # Přidat odkaz na nadřazenou složku
                if path != "/":
                    parent_item = QTreeWidgetItem(self.remote_tree)
                    parent_item.setText(0, "..")
                    parent_item.setText(2, "📁 Složka")
                    parent_path = "/".join(path.rstrip("/").split("/")[:-1])
                    if not parent_path:
                        parent_path = "/"
                    parent_item.setData(0, Qt.UserRole, parent_path)
                
                # Načíst obsah
                for item in self.sftp_client.listdir_attr(path):
                    tree_item = QTreeWidgetItem(self.remote_tree)
                    tree_item.setText(0, item.filename)
                    tree_item.setData(0, Qt.UserRole, f"{path.rstrip('/')}/{item.filename}")
                    
                    if stat.S_ISDIR(item.st_mode):
                        tree_item.setText(2, "📁 Složka")
                    else:
                        tree_item.setText(1, self.format_size(item.st_size))
                        tree_item.setText(2, "📄 Soubor")
        
        except Exception as e:
            QMessageBox.warning(self, "Chyba", f"Nelze načíst vzdálenou složku:\n{str(e)}")
    
    def format_size(self, size):
        """Formátovat velikost souboru"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def local_item_double_clicked(self, item, column):
        """Dvoj-klik na lokální položku"""
        path = item.data(0, Qt.UserRole)
        if os.path.isdir(path):
            self.local_path_input.setText(path)
            self.refresh_local_files()
    
    def remote_item_double_clicked(self, item, column):
        """Dvoj-klik na vzdálenou položku"""
        path = item.data(0, Qt.UserRole)
        if item.text(2) == "📁 Složka":
            self.remote_path_input.setText(path)
            self.refresh_remote_files()
    
    def local_context_menu(self, position):
        """Kontextové menu pro lokální soubory"""
        menu = QMenu()
        
        new_folder_action = menu.addAction("🆕 Nová složka")
        delete_action = menu.addAction("🗑️ Smazat")
        refresh_action = menu.addAction("🔄 Obnovit")
        
        action = menu.exec_(self.local_tree.mapToGlobal(position))
        
        if action == new_folder_action:
            self.create_local_folder()
        elif action == delete_action:
            self.delete_local_item()
        elif action == refresh_action:
            self.refresh_local_files()
    
    def remote_context_menu(self, position):
        """Kontextové menu pro vzdálené soubory"""
        if not self.ftp_client and not self.sftp_client:
            return
        
        menu = QMenu()
        
        new_folder_action = menu.addAction("🆕 Nová složka")
        delete_action = menu.addAction("🗑️ Smazat")
        refresh_action = menu.addAction("🔄 Obnovit")
        
        action = menu.exec_(self.remote_tree.mapToGlobal(position))
        
        if action == new_folder_action:
            self.create_remote_folder()
        elif action == delete_action:
            self.delete_remote_item()
        elif action == refresh_action:
            self.refresh_remote_files()
    
    def create_local_folder(self):
        """Vytvořit lokální složku"""
        name, ok = QInputDialog.getText(self, "Nová složka", "Název složky:")
        if ok and name:
            try:
                new_path = os.path.join(self.current_local_path, name)
                os.makedirs(new_path)
                self.refresh_local_files()
            except Exception as e:
                QMessageBox.critical(self, "Chyba", f"Nelze vytvořit složku:\n{str(e)}")
    
    def create_remote_folder(self):
        """Vytvořit vzdálenou složku"""
        name, ok = QInputDialog.getText(self, "Nová složka", "Název složky:")
        if ok and name:
            try:
                if self.ftp_client:
                    self.ftp_client.mkd(name)
                elif self.sftp_client:
                    new_path = f"{self.current_remote_path.rstrip('/')}/{name}"
                    self.sftp_client.mkdir(new_path)
                self.refresh_remote_files()
            except Exception as e:
                QMessageBox.critical(self, "Chyba", f"Nelze vytvořit složku:\n{str(e)}")
    
    def delete_local_item(self):
        """Smazat lokální položku"""
        item = self.local_tree.currentItem()
        if not item or item.text(0) == "..":
            return
        
        path = item.data(0, Qt.UserRole)
        reply = QMessageBox.question(
            self,
            "Potvrzení",
            f"Opravdu chcete smazat '{os.path.basename(path)}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                if os.path.isdir(path):
                    import shutil
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                self.refresh_local_files()
            except Exception as e:
                QMessageBox.critical(self, "Chyba", f"Nelze smazat:\n{str(e)}")
    
    def delete_remote_item(self):
        """Smazat vzdálenou položku"""
        item = self.remote_tree.currentItem()
        if not item or item.text(0) == "..":
            return
        
        name = item.text(0)
        reply = QMessageBox.question(
            self,
            "Potvrzení",
            f"Opravdu chcete smazat '{name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                if self.ftp_client:
                    if item.text(2) == "📁 Složka":
                        self.ftp_client.rmd(name)
                    else:
                        self.ftp_client.delete(name)
                elif self.sftp_client:
                    path = item.data(0, Qt.UserRole)
                    if item.text(2) == "📁 Složka":
                        self.sftp_client.rmdir(path)
                    else:
                        self.sftp_client.remove(path)
                self.refresh_remote_files()
            except Exception as e:
                QMessageBox.critical(self, "Chyba", f"Nelze smazat:\n{str(e)}")
    
    def upload_file(self):
        """Nahrát soubor na server"""
        item = self.local_tree.currentItem()
        if not item or item.text(2) != "📄 Soubor":
            QMessageBox.warning(self, "FORTEftp", "Vyberte soubor k nahrání!")
            return
        
        local_path = item.data(0, Qt.UserRole)
        filename = os.path.basename(local_path)
        
        try:
            if self.ftp_client:
                with open(local_path, 'rb') as f:
                    self.ftp_client.storbinary(f'STOR {filename}', f)
            elif self.sftp_client:
                remote_path = f"{self.current_remote_path.rstrip('/')}/{filename}"
                self.sftp_client.put(local_path, remote_path)
            
            QMessageBox.information(self, "Úspěch", f"Soubor '{filename}' byl nahrán.")
            self.refresh_remote_files()
        
        except Exception as e:
            QMessageBox.critical(self, "Chyba", f"Nelze nahrát soubor:\n{str(e)}")
    
    def download_file(self):
        """Stáhnout soubor ze serveru"""
        item = self.remote_tree.currentItem()
        if not item or item.text(2) != "📄 Soubor":
            QMessageBox.warning(self, "FORTEftp", "Vyberte soubor ke stažení!")
            return
        
        filename = item.text(0)
        local_path = os.path.join(self.current_local_path, filename)
        
        try:
            if self.ftp_client:
                with open(local_path, 'wb') as f:
                    self.ftp_client.retrbinary(f'RETR {filename}', f.write)
            elif self.sftp_client:
                remote_path = item.data(0, Qt.UserRole)
                self.sftp_client.get(remote_path, local_path)
            
            QMessageBox.information(self, "Úspěch", f"Soubor '{filename}' byl stažen.")
            self.refresh_local_files()
        
        except Exception as e:
            QMessageBox.critical(self, "Chyba", f"Nelze stáhnout soubor:\n{str(e)}")
    
    def upload_modified_files(self):
        """Nahrát pouze změněné soubory z aktuální lokální složky"""
        if not self.ftp_client and not self.sftp_client:
            QMessageBox.warning(self, "FORTEftp", "Nejste připojeni k serveru!")
            return
        
        # Zobrazit dialog s volbami
        dialog = QDialog(self)
        dialog.setWindowTitle("Synchronizace souborů")
        dialog.setModal(True)
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # Popis
        desc_label = QLabel("Spustit kontrolu a synchronizaci souborů?")
        desc_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(desc_label)
        
        layout.addSpacing(10)
        
        info_label = QLabel("Program zkontroluje všechny soubory v aktuální složce\na nahraje pouze nové nebo změněné soubory na server.")
        layout.addWidget(info_label)
        
        layout.addSpacing(15)
        
        # Checkbox pro mazání
        delete_checkbox = QCheckBox("Smazat soubory, které nejsou lokálně uložené")
        delete_checkbox.setStyleSheet("font-weight: bold; color: #d32f2f;")
        layout.addWidget(delete_checkbox)
        
        warning_label = QLabel("⚠️ Pokud je tato volba zaškrtnuta, soubory na serveru,\nkteré neexistují v lokální složce, budou SMAZÁNY!")
        warning_label.setStyleSheet("color: #d32f2f; font-size: 9pt; margin-left: 25px;")
        layout.addWidget(warning_label)
        
        layout.addSpacing(20)
        
        # Tlačítka
        btn_layout = QHBoxLayout()
        start_btn = QPushButton("▶️ Spustit kontrolu")
        start_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 8px 16px; font-weight: bold; }")
        start_btn.clicked.connect(dialog.accept)
        
        cancel_btn = QPushButton("Zrušit")
        cancel_btn.clicked.connect(dialog.reject)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(start_btn)
        layout.addLayout(btn_layout)
        
        dialog.setLayout(layout)
        
        # Pokud uživatel zruší, ukončit
        if dialog.exec_() != QDialog.Accepted:
            return
        
        delete_remote_files = delete_checkbox.isChecked()
        
        # Získat seznam lokálních souborů
        local_files = []
        try:
            for item in Path(self.current_local_path).rglob('*'):
                if item.is_file():
                    rel_path = item.relative_to(self.current_local_path)
                    local_files.append({
                        'path': str(item),
                        'rel_path': str(rel_path).replace('\\', '/'),
                        'size': item.stat().st_size,
                        'mtime': item.stat().st_mtime
                    })
        except Exception as e:
            QMessageBox.critical(self, "Chyba", f"Nelze načíst lokální soubory:\n{str(e)}")
            return
        
        if not local_files:
            QMessageBox.information(self, "FORTEftp", "Žádné soubory k nahrání.")
            return
        
        # Porovnat se vzdálenými soubory
        files_to_upload = []
        
        progress = QProgressDialog("Kontrolujem změny...", "Zrušit", 0, len(local_files), self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setWindowTitle("Analýza souborů")
        
        for idx, local_file in enumerate(local_files):
            if progress.wasCanceled():
                return
            
            progress.setValue(idx)
            progress.setLabelText(f"Kontroluji: {local_file['rel_path']}")
            QApplication.processEvents()
            
            remote_path = f"{self.current_remote_path.rstrip('/')}/{local_file['rel_path']}"
            should_upload = False
            reason = ""
            
            try:
                if self.ftp_client:
                    # Zkusit získat velikost vzdáleného souboru
                    try:
                        remote_size = self.ftp_client.size(local_file['rel_path'])
                        # Soubor existuje - porovnat velikost
                        if remote_size is None or remote_size != local_file['size']:
                            should_upload = True
                            reason = "Jiná velikost"
                        else:
                            # Velikost je stejná, zkusit porovnat čas
                            try:
                                mdtm_response = self.ftp_client.voidcmd(f"MDTM {local_file['rel_path']}")
                                # Odpověď je ve formátu: "213 YYYYMMDDhhmmss"
                                if mdtm_response.startswith('213 '):
                                    import time
                                    from datetime import datetime
                                    time_str = mdtm_response[4:].strip()
                                    remote_time = datetime.strptime(time_str, '%Y%m%d%H%M%S').timestamp()
                                    # Porovnat s tolerancí 2 sekundy (kvůli zaokrouhlení)
                                    if local_file['mtime'] > remote_time + 2:
                                        should_upload = True
                                        reason = "Novější verze"
                            except:
                                # MDTM není podporováno nebo selhalo - soubor necháme
                                pass
                    except:
                        # Soubor neexistuje na serveru
                        should_upload = True
                        reason = "Nový soubor"
                
                elif self.sftp_client:
                    # SFTP kontrola
                    try:
                        remote_stat = self.sftp_client.stat(remote_path)
                        # Nejdřív porovnat velikost
                        if local_file['size'] != remote_stat.st_size:
                            should_upload = True
                            reason = "Jiná velikost"
                        # Pak porovnat čas modifikace s tolerancí 2 sekundy
                        elif local_file['mtime'] > remote_stat.st_mtime + 2:
                            should_upload = True
                            reason = "Novější verze"
                    except FileNotFoundError:
                        should_upload = True
                        reason = "Nový soubor"
                    except:
                        # Jiná chyba - přeskočit soubor
                        pass
                
                if should_upload:
                    files_to_upload.append({
                        'local': local_file['path'],
                        'remote': remote_path,
                        'rel_path': local_file['rel_path'],
                        'size': local_file['size'],
                        'reason': reason
                    })
            
            except Exception as e:
                # Při neočekávané chybě pouze logovat, ale nepřidávat
                print(f"Chyba při kontrole {local_file['rel_path']}: {e}")
        
        progress.setValue(len(local_files))
        
        # Pokud je aktivní mazání, najít soubory ke smazání
        files_to_delete = []
        if delete_remote_files:
            progress_delete = QProgressDialog("Kontroluji soubory ke smazání...", "Zrušit", 0, 100, self)
            progress_delete.setWindowModality(Qt.WindowModal)
            progress_delete.setWindowTitle("Hledání souborů")
            progress_delete.setValue(10)
            QApplication.processEvents()
            
            # Získat seznam vzdálených souborů
            remote_files_list = []
            try:
                if self.ftp_client:
                    remote_files_list = self.get_all_remote_files_ftp(self.current_remote_path)
                elif self.sftp_client:
                    remote_files_list = self.get_all_remote_files_sftp(self.current_remote_path)
            except Exception as e:
                QMessageBox.warning(self, "Chyba", f"Nelze načíst vzdálené soubory:\n{str(e)}")
            
            progress_delete.setValue(50)
            QApplication.processEvents()
            
            # Vytvořit set lokálních relativních cest
            local_paths_set = {f['rel_path'] for f in local_files}
            
            # Najít soubory které jsou na serveru, ale ne lokálně
            for remote_file in remote_files_list:
                if remote_file['rel_path'] not in local_paths_set:
                    files_to_delete.append(remote_file)
            
            progress_delete.setValue(100)

        # Uživatel vybere soubory k nahrání
        files_to_upload = self.select_files_to_upload(files_to_upload)
        if files_to_upload is None:
            return
        
        # Připravit zprávu
        has_changes = len(files_to_upload) > 0 or len(files_to_delete) > 0
        
        if not has_changes:
            QMessageBox.information(
                self, 
                "FORTEftp", 
                "✅ Všechny soubory jsou synchronizované!\n\nŽádné změny k provedení."
            )
            return
        
        # Zobrazit dialog s potvrzením
        message = "NALEZENÉ ZMĚNY:\n\n"
        
        if files_to_upload:
            total_size = sum(f['size'] for f in files_to_upload)
            message += f"📤 NAHRÁT: {len(files_to_upload)} souborů ({self.format_size(total_size)})\n\n"
            
            # Zobrazit max 8 souborů
            for f in files_to_upload[:8]:
                message += f"  ⬆️ {f['rel_path']} - {f['reason']}\n"
            
            if len(files_to_upload) > 8:
                message += f"  ... a {len(files_to_upload) - 8} dalších\n"
        
        if files_to_delete:
            message += f"\n🗑️ SMAZAT: {len(files_to_delete)} souborů\n\n"
            
            # Zobrazit max 8 souborů
            for f in files_to_delete[:8]:
                message += f"  ❌ {f['rel_path']}\n"
            
            if len(files_to_delete) > 8:
                message += f"  ... a {len(files_to_delete) - 8} dalších\n"
        
        message += "\nPokračovat se synchronizací?"
        
        reply = QMessageBox.question(
            self,
            "Potvrzení synchronizace",
            message,
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Provést operace
        total_operations = len(files_to_upload) + len(files_to_delete)
        sync_progress = QProgressDialog("Synchronizuji...", "Zrušit", 0, total_operations, self)
        sync_progress.setWindowModality(Qt.WindowModal)
        sync_progress.setWindowTitle("Synchronizace")
        
        upload_success = 0
        delete_success = 0
        failed_files = []
        current_op = 0
        
        # Nahrát soubory
        for idx, file_info in enumerate(files_to_upload):
            if sync_progress.wasCanceled():
                break
            
            sync_progress.setValue(current_op)
            sync_progress.setLabelText(f"⬆️ Nahrávám ({idx + 1}/{len(files_to_upload)}): {file_info['rel_path']}")
            QApplication.processEvents()
            
            try:
                if self.ftp_client:
                    # Vytvořit vzdálené složky pokud neexistují
                    remote_dir = '/'.join(file_info['remote'].split('/')[:-1])
                    self.create_remote_directories_ftp(remote_dir)
                    
                    # Nahrát soubor
                    with open(file_info['local'], 'rb') as f:
                        filename = file_info['rel_path'].split('/')[-1]
                        self.ftp_client.cwd(remote_dir if remote_dir else '/')
                        self.ftp_client.storbinary(f'STOR {filename}', f)
                        self.ftp_client.cwd(self.current_remote_path)
                
                elif self.sftp_client:
                    # Vytvořit vzdálené složky pokud neexistují
                    remote_dir = '/'.join(file_info['remote'].split('/')[:-1])
                    self.create_remote_directories_sftp(remote_dir)
                    
                    # Nahrát soubor
                    self.sftp_client.put(file_info['local'], file_info['remote'])
                
                upload_success += 1
            
            except Exception as e:
                failed_files.append(('Nahrání', file_info['rel_path'], str(e)))
            
            current_op += 1
        
        # Smazat soubory
        for idx, file_info in enumerate(files_to_delete):
            if sync_progress.wasCanceled():
                break
            
            sync_progress.setValue(current_op)
            sync_progress.setLabelText(f"🗑️ Mažu ({idx + 1}/{len(files_to_delete)}): {file_info['rel_path']}")
            QApplication.processEvents()
            
            try:
                if self.ftp_client:
                    if file_info['is_dir']:
                        self.delete_remote_dir_ftp(file_info['full_path'])
                    else:
                        self.ftp_client.delete(file_info['full_path'])
                
                elif self.sftp_client:
                    if file_info['is_dir']:
                        self.delete_remote_dir_sftp(file_info['full_path'])
                    else:
                        self.sftp_client.remove(file_info['full_path'])
                
                delete_success += 1
            
            except Exception as e:
                failed_files.append(('Mazání', file_info['rel_path'], str(e)))
            
            current_op += 1
        
        sync_progress.setValue(total_operations)
        
        # Zobrazit výsledek
        result_msg = "VÝSLEDEK SYNCHRONIZACE:\n\n"
        
        if files_to_upload:
            result_msg += f"⬆️ Nahráno: {upload_success}/{len(files_to_upload)} souborů\n"
        
        if files_to_delete:
            result_msg += f"🗑️ Smazáno: {delete_success}/{len(files_to_delete)} souborů\n"
        
        if failed_files:
            result_msg += f"\n❌ Chyby ({len(failed_files)}):\n"
            for operation, fname, error in failed_files[:5]:
                result_msg += f"  • [{operation}] {fname}: {error}\n"
            if len(failed_files) > 5:
                result_msg += f"  ... a {len(failed_files) - 5} dalších\n"
        
        if not failed_files:
            result_msg += "\n✅ Synchronizace dokončena bez chyb!"
        
        QMessageBox.information(self, "Výsledek synchronizace", result_msg)
        self.refresh_remote_files()

    def select_files_to_upload(self, files_to_upload):
        """Dialog pro výběr souborů k nahrání"""
        if not files_to_upload:
            return []

        dialog = QDialog(self)
        dialog.setWindowTitle("Výběr souborů k nahrání")
        dialog.setModal(True)
        dialog.setMinimumWidth(600)

        layout = QVBoxLayout()

        title_label = QLabel("Vyberte soubory, které chcete nahrát na server")
        title_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        layout.addWidget(title_label)

        layout.addSpacing(8)

        select_all_checkbox = QCheckBox("Vybrat vše")
        select_all_checkbox.setChecked(True)
        layout.addWidget(select_all_checkbox)

        files_tree = QTreeWidget()
        files_tree.setHeaderLabels(["Soubor", "Důvod", "Velikost"])
        files_tree.setRootIsDecorated(False)
        files_tree.setAlternatingRowColors(True)
        files_tree.setSelectionMode(QTreeWidget.NoSelection)
        files_tree.setColumnWidth(0, 360)
        layout.addWidget(files_tree)

        for file_info in files_to_upload:
            item = QTreeWidgetItem([
                file_info['rel_path'],
                file_info.get('reason', ''),
                self.format_size(file_info.get('size', 0))
            ])
            item.setCheckState(0, Qt.Checked)
            item.setData(0, Qt.UserRole, file_info)
            files_tree.addTopLevelItem(item)

        summary_label = QLabel()
        layout.addWidget(summary_label)

        def update_summary():
            selected_count = 0
            total_size = 0
            for i in range(files_tree.topLevelItemCount()):
                item = files_tree.topLevelItem(i)
                if item.checkState(0) == Qt.Checked:
                    selected_count += 1
                    file_data = item.data(0, Qt.UserRole)
                    total_size += file_data.get('size', 0)
            summary_label.setText(
                f"Vybráno: {selected_count}/{len(files_to_upload)} souborů ({self.format_size(total_size)})"
            )

        def refresh_select_all_state():
            checked = 0
            total = files_tree.topLevelItemCount()
            for i in range(total):
                if files_tree.topLevelItem(i).checkState(0) == Qt.Checked:
                    checked += 1

            select_all_checkbox.blockSignals(True)
            if checked == 0:
                select_all_checkbox.setCheckState(Qt.Unchecked)
            elif checked == total:
                select_all_checkbox.setCheckState(Qt.Checked)
            else:
                select_all_checkbox.setCheckState(Qt.PartiallyChecked)
            select_all_checkbox.blockSignals(False)

        def on_select_all_changed(state):
            if state == Qt.PartiallyChecked:
                return
            files_tree.blockSignals(True)
            new_state = Qt.Checked if state == Qt.Checked else Qt.Unchecked
            for i in range(files_tree.topLevelItemCount()):
                files_tree.topLevelItem(i).setCheckState(0, new_state)
            files_tree.blockSignals(False)
            update_summary()

        def on_item_changed(item, column):
            if column == 0:
                update_summary()
                refresh_select_all_state()

        select_all_checkbox.setTristate(True)
        select_all_checkbox.stateChanged.connect(on_select_all_changed)
        files_tree.itemChanged.connect(on_item_changed)

        update_summary()
        refresh_select_all_state()

        layout.addSpacing(10)

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Zrušit")
        cancel_btn.clicked.connect(dialog.reject)
        continue_btn = QPushButton("✅ Pokračovat")
        continue_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 6px 14px; font-weight: bold; }")
        continue_btn.clicked.connect(dialog.accept)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(continue_btn)
        layout.addLayout(btn_layout)

        dialog.setLayout(layout)

        if dialog.exec_() != QDialog.Accepted:
            return None

        selected_files = []
        for i in range(files_tree.topLevelItemCount()):
            item = files_tree.topLevelItem(i)
            if item.checkState(0) == Qt.Checked:
                selected_files.append(item.data(0, Qt.UserRole))

        return selected_files
    
    def create_remote_directories_ftp(self, path):
        """Vytvořit vzdálené složky přes FTP"""
        if not path or path == '/':
            return
        
        parts = path.strip('/').split('/')
        current = ''
        
        for part in parts:
            current += '/' + part
            try:
                self.ftp_client.cwd(current)
            except:
                try:
                    self.ftp_client.mkd(current)
                except:
                    pass
    
    def create_remote_directories_sftp(self, path):
        """Vytvořit vzdálené složky přes SFTP"""
        if not path or path == '/':
            return
        
        parts = path.strip('/').split('/')
        current = ''
        
        for part in parts:
            current += '/' + part
            try:
                self.sftp_client.stat(current)
            except:
                try:
                    self.sftp_client.mkdir(current)
                except:
                    pass
    
    def get_all_remote_files_ftp(self, base_path):
        """Získat seznam všech vzdálených souborů přes FTP (rekurzivně)"""
        all_files = []
        
        def scan_directory(path):
            try:
                self.ftp_client.cwd(path)
                items = []
                self.ftp_client.dir(items.append)
                
                for item in items:
                    parts = item.split()
                    if len(parts) < 9:
                        continue
                    
                    name = " ".join(parts[8:])
                    if name in ['.', '..']:
                        continue
                    
                    full_path = f"{path.rstrip('/')}/{name}"
                    rel_path = full_path.replace(base_path.rstrip('/') + '/', '', 1)
                    
                    is_dir = item.startswith('d')
                    
                    all_files.append({
                        'rel_path': rel_path,
                        'full_path': full_path,
                        'is_dir': is_dir
                    })
                    
                    if is_dir:
                        scan_directory(full_path)
            except:
                pass
        
        scan_directory(base_path)
        return all_files
    
    def get_all_remote_files_sftp(self, base_path):
        """Získat seznam všech vzdálených souborů přes SFTP (rekurzivně)"""
        all_files = []
        
        def scan_directory(path):
            try:
                for item in self.sftp_client.listdir_attr(path):
                    full_path = f"{path.rstrip('/')}/{item.filename}"
                    rel_path = full_path.replace(base_path.rstrip('/') + '/', '', 1)
                    
                    is_dir = stat.S_ISDIR(item.st_mode)
                    
                    all_files.append({
                        'rel_path': rel_path,
                        'full_path': full_path,
                        'is_dir': is_dir
                    })
                    
                    if is_dir:
                        scan_directory(full_path)
            except:
                pass
        
        scan_directory(base_path)
        return all_files
    
    def delete_remote_dir_ftp(self, path):
        """Smazat složku a veškerý obsah přes FTP"""
        try:
            items = []
            self.ftp_client.cwd(path)
            self.ftp_client.dir(items.append)
            
            for item in items:
                parts = item.split()
                if len(parts) < 9:
                    continue
                
                name = " ".join(parts[8:])
                if name in ['.', '..']:
                    continue
                
                full_path = f"{path.rstrip('/')}/{name}"
                
                if item.startswith('d'):
                    self.delete_remote_dir_ftp(full_path)
                else:
                    self.ftp_client.delete(full_path)
            
            # Vrátit se zpět a smazat prázdnou složku
            parent = '/'.join(path.rstrip('/').split('/')[:-1])
            if parent:
                self.ftp_client.cwd(parent)
            else:
                self.ftp_client.cwd('/')
            self.ftp_client.rmd(path)
        except:
            pass
    
    def delete_remote_dir_sftp(self, path):
        """Smazat složku a veškerý obsah přes SFTP"""
        try:
            for item in self.sftp_client.listdir_attr(path):
                full_path = f"{path.rstrip('/')}/{item.filename}"
                
                if stat.S_ISDIR(item.st_mode):
                    self.delete_remote_dir_sftp(full_path)
                else:
                    self.sftp_client.remove(full_path)
            
            self.sftp_client.rmdir(path)
        except:
            pass
    
    def closeEvent(self, event):
        """Uzavření aplikace"""
        self.disconnect()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Nastavit ikonu aplikace
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    window = FORTEftp()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QPushButton, QTextEdit, QLabel, 
                           QFileDialog, QComboBox, QProgressBar, QMessageBox,
                           QCheckBox, QSplitter, QDialog, QLineEdit, QDoubleSpinBox,
                           QSpinBox, QGroupBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPalette, QColor
from novel_to_audio import NovelToAudio
import json

class NovelProcessThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    log = pyqtSignal(str)  # 新增日志信号
    dialogues_ready = pyqtSignal(list)  # 新增对话列表信号
    
    def __init__(self, novel_text, output_path, split_only=False, voice_data=None):
        super().__init__()
        self.novel_text = novel_text
        self.output_path = output_path
        self.split_only = split_only
        self.processor = NovelToAudio()
        if voice_data:
            self.processor.voice_data = voice_data
        self.dialogues = None  # 存储分割后的对话
        
        # 从主窗口获取旁白开关状态并设置
        main_window = QApplication.activeWindow()
        if isinstance(main_window, MainWindow):
            self.processor.set_narration(main_window.narration_checkbox.isChecked())
    
    def run(self):
        try:
            if not self.dialogues:  # 如果没有已分割的对话，则进行分割
                # 分割对话
                self.log.emit("开始分割对话...")
                self.log.emit("正在调用AI进行对话分割...")
                
                self.dialogues = self.processor.split_dialogue(self.novel_text, callback=self.log.emit)
                self.progress.emit(30)
                self.log.emit(f"分割完成，共识别出 {len(self.dialogues)} 段对话")
                
                # 保存分割结果
                self.log.emit("保存分割结果...")
                with open('dialogue_split.json', 'w', encoding='utf-8') as f:
                    import json
                    json.dump(self.dialogues, f, ensure_ascii=False, indent=2)
                self.progress.emit(40)
                self.log.emit("分割结果已保存到 dialogue_split.json")
                
                # 发送对话列表信号
                self.dialogues_ready.emit(self.dialogues)
            
            if self.split_only:
                self.progress.emit(100)
                self.finished.emit(True, "文本分割完成！结果已保存到dialogue_split.json")
                return
            
            # 生成音频文件
            self.log.emit("开始生成音频...")
            audio_files = []
            total_dialogues = len(self.dialogues)
            
            for i, dialogue in enumerate(self.dialogues):
                self.log.emit(f"正在处理第 {i+1}/{total_dialogues} 段对话: {dialogue['role']}")
                audio_path = self.processor.text_to_speech(dialogue['text'], dialogue['role'])
                audio_files.append(audio_path)
                progress = 40 + int((i + 1) / total_dialogues * 50)
                self.progress.emit(progress)
            
            # 合并音频
            self.log.emit("正在合并音频文件...")
            self.processor.merge_audio(audio_files, self.output_path)
            self.progress.emit(100)
            self.log.emit("音频合并完成！")
            
            self.finished.emit(True, "处理完成！")
        except Exception as e:
            self.log.emit(f"错误: {str(e)}")
            self.finished.emit(False, f"处理出错: {str(e)}")

class AIChatThread(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    token = pyqtSignal(str)  # 新增token信号
    
    def __init__(self, processor, message):
        super().__init__()
        self.processor = processor
        self.message = message
    
    def run(self):
        try:
            def token_callback(token):
                self.token.emit(token)
            
            response = self.processor.chat_with_ai(self.message, token_callback)
            self.finished.emit(response)
        except Exception as e:
            self.error.emit(str(e))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("有声小说生成器")
        self.setMinimumSize(1200, 800)
        
        # 检测系统主题
        self.is_dark_theme = self.is_system_dark_theme()
        
        # 设置应用样式
        self.update_theme()
        
        # 创建NovelToAudio实例
        self.processor = NovelToAudio()
        
        # 加载默认搜索路径设置
        self.load_default_paths()
        
        # 创建主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # 创建主布局
        main_layout = QHBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_widget.setLayout(main_layout)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # 左侧面板
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_panel.setLayout(left_layout)
        
        # 添加控件到左侧面板
        # 1. 输入区域
        input_group = QGroupBox("输入小说文本")
        input_layout = QVBoxLayout()
        input_layout.setSpacing(5)
        self.text_edit = QTextEdit()
        input_layout.addWidget(self.text_edit)
        input_group.setLayout(input_layout)
        left_layout.addWidget(input_group)
        
        # 2. 角色音色设置（初始隐藏）
        self.voice_settings_widget = QWidget()
        voice_layout = QVBoxLayout()
        voice_layout.setSpacing(10)
        self.voice_settings_widget.setLayout(voice_layout)
        
        # 创建角色音色设置的容器
        self.voice_settings_container = QWidget()
        self.voice_settings_layout = QVBoxLayout()
        self.voice_settings_layout.setSpacing(10)
        self.voice_settings_container.setLayout(self.voice_settings_layout)
        
        # 添加标题标签
        voice_label = QLabel("角色音色设置")
        voice_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333333;")
        self.voice_settings_layout.addWidget(voice_label)
        
        # 添加默认角色（旁白）
        self.voice_settings = {}
        self.voice_data = {}  # 存储每个角色的音色设置数据
        self.add_voice_setting("旁白")
        
        # 将容器添加到主布局
        voice_layout.addWidget(self.voice_settings_container)
        
        # 初始时隐藏角色音色设置
        self.voice_settings_widget.hide()
        left_layout.addWidget(self.voice_settings_widget)
        
        # 3. 进度条
        progress_group = QGroupBox("处理进度")
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(5)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumHeight(20)
        progress_layout.addWidget(self.progress_bar)
        progress_group.setLayout(progress_layout)
        left_layout.addWidget(progress_group)
        
        # 4. 操作按钮
        button_group = QHBoxLayout()
        button_group.setSpacing(10)
        
        # 分割按钮
        self.split_btn = QPushButton("文本分割")
        self.split_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_MediaPlay))
        self.split_btn.clicked.connect(self.start_split)
        button_group.addWidget(self.split_btn)
        
        # 选择输出文件按钮
        self.select_output_btn = QPushButton("选择输出文件")
        self.select_output_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DialogOpenButton))
        self.select_output_btn.clicked.connect(self.select_output_file)
        button_group.addWidget(self.select_output_btn)
        
        # 生成按钮（初始禁用）
        self.generate_btn = QPushButton("生成音频")
        self.generate_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_MediaVolume))
        self.generate_btn.clicked.connect(self.start_generate)
        self.generate_btn.setEnabled(False)
        button_group.addWidget(self.generate_btn)
        
        left_layout.addLayout(button_group)
        
        # 右侧面板 - 日志显示
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setSpacing(10)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_panel.setLayout(right_layout)
        
        # AI对话区域
        ai_group = self.setup_ai_chat_area()
        right_layout.addWidget(ai_group)
        
        # 日志显示区域
        log_group = QGroupBox("处理日志")
        log_layout = QVBoxLayout()
        log_layout.setSpacing(5)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        right_layout.addWidget(log_group)
        
        # 控制按钮区域
        control_group = QGroupBox("控制面板")
        control_layout = QVBoxLayout()
        control_layout.setSpacing(10)
        
        # 添加默认搜索路径按钮
        default_path_btn = QPushButton("默认搜索路径")
        default_path_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DirIcon))
        default_path_btn.clicked.connect(self.show_default_path_dialog)
        control_layout.addWidget(default_path_btn)
        
        # 添加GPTSoVITS测试按钮
        test_btn = QPushButton("GPTSoVITS测试")
        test_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileIcon))
        test_btn.clicked.connect(self.show_gptsovits_test_dialog)
        control_layout.addWidget(test_btn)
        
        # 添加AI模型设置按钮
        ai_model_btn = QPushButton("AI分割模型选择")
        ai_model_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        ai_model_btn.clicked.connect(self.show_ai_model_dialog)
        control_layout.addWidget(ai_model_btn)
        
        # 添加旁白开关
        narration_layout = QHBoxLayout()
        self.narration_checkbox = QCheckBox("启用旁白")
        self.narration_checkbox.setChecked(True)
        narration_layout.addWidget(self.narration_checkbox)
        control_layout.addLayout(narration_layout)
        
        control_group.setLayout(control_layout)
        right_layout.addWidget(control_group)
        
        # 添加面板到分割器
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        
        # 设置分割器的初始大小
        splitter.setSizes([600, 600])
        
        self.output_path = None
        self.dialogues = None
        
        # 创建音色编辑对话框
        self.voice_edit_dialog = None
        
        # 创建默认路径设置对话框
        self.default_path_dialog = None
        
        # 创建GPTSoVITS测试对话框
        self.gptsovits_test_dialog = None
        
        # 创建AI模型设置对话框
        self.ai_model_dialog = None
        
        self.chat_thread = None  # 添加chat_thread属性
        self.is_chatting = False  # 添加聊天状态标志
    
    def is_system_dark_theme(self):
        """检测系统是否为暗色主题"""
        palette = self.palette()
        return palette.color(QPalette.ColorRole.Window).lightness() < 128
    
    def update_theme(self):
        """更新界面主题"""
        if self.is_dark_theme:
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #1e1e1e;
                }
                QWidget {
                    font-family: "Microsoft YaHei", "SimHei", sans-serif;
                }
                QPushButton {
                    background-color: #2d2d2d;
                    color: #ffffff;
                    border: 1px solid #3d3d3d;
                    padding: 8px 16px;
                    border-radius: 4px;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #3d3d3d;
                    border-color: #4d4d4d;
                }
                QPushButton:disabled {
                    background-color: #2d2d2d;
                    border-color: #2d2d2d;
                    color: #666666;
                }
                QTextEdit {
                    border: 1px solid #3d3d3d;
                    border-radius: 4px;
                    padding: 8px;
                    background-color: #2d2d2d;
                    color: #ffffff;
                }
                QLabel {
                    color: #ffffff;
                }
                QProgressBar {
                    border: 1px solid #3d3d3d;
                    border-radius: 4px;
                    text-align: center;
                    background-color: #2d2d2d;
                }
                QProgressBar::chunk {
                    background-color: #4d4d4d;
                    border-radius: 3px;
                }
                QComboBox {
                    border: 1px solid #3d3d3d;
                    border-radius: 4px;
                    padding: 5px;
                    background-color: #2d2d2d;
                    color: #ffffff;
                }
                QLineEdit {
                    border: 1px solid #3d3d3d;
                    border-radius: 4px;
                    padding: 5px;
                    background-color: #2d2d2d;
                    color: #ffffff;
                }
                QGroupBox {
                    border: 1px solid #3d3d3d;
                    border-radius: 4px;
                    margin-top: 12px;
                    padding-top: 16px;
                    background-color: #2d2d2d;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                    color: #ffffff;
                    font-weight: bold;
                }
                QCheckBox {
                    color: #ffffff;
                }
                QSpinBox, QDoubleSpinBox {
                    border: 1px solid #3d3d3d;
                    border-radius: 4px;
                    padding: 5px;
                    background-color: #2d2d2d;
                    color: #ffffff;
                }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #ffffff;
                }
                QWidget {
                    font-family: "Microsoft YaHei", "SimHei", sans-serif;
                }
                QPushButton {
                    background-color: #f5f5f5;
                    color: #333333;
                    border: 1px solid #dddddd;
                    padding: 8px 16px;
                    border-radius: 4px;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #e8e8e8;
                    border-color: #cccccc;
                }
                QPushButton:disabled {
                    background-color: #f5f5f5;
                    border-color: #f5f5f5;
                    color: #999999;
                }
                QTextEdit {
                    border: 1px solid #dddddd;
                    border-radius: 4px;
                    padding: 8px;
                    background-color: #ffffff;
                }
                QLabel {
                    color: #333333;
                }
                QProgressBar {
                    border: 1px solid #dddddd;
                    border-radius: 4px;
                    text-align: center;
                    background-color: #ffffff;
                }
                QProgressBar::chunk {
                    background-color: #e8e8e8;
                    border-radius: 3px;
                }
                QComboBox {
                    border: 1px solid #dddddd;
                    border-radius: 4px;
                    padding: 5px;
                    background-color: #ffffff;
                }
                QLineEdit {
                    border: 1px solid #dddddd;
                    border-radius: 4px;
                    padding: 5px;
                    background-color: #ffffff;
                }
                QGroupBox {
                    border: 1px solid #dddddd;
                    border-radius: 4px;
                    margin-top: 12px;
                    padding-top: 16px;
                    background-color: #ffffff;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                    color: #333333;
                    font-weight: bold;
                }
                QCheckBox {
                    color: #333333;
                }
                QSpinBox, QDoubleSpinBox {
                    border: 1px solid #dddddd;
                    border-radius: 4px;
                    padding: 5px;
                    background-color: #ffffff;
                }
            """)
    
    def changeEvent(self, event):
        """处理窗口状态改变事件"""
        if event.type() == event.Type.WindowStateChange:
            # 检测系统主题是否改变
            new_is_dark = self.is_system_dark_theme()
            if new_is_dark != self.is_dark_theme:
                self.is_dark_theme = new_is_dark
                self.update_theme()
        super().changeEvent(event)
    
    def load_default_paths(self):
        """从配置文件加载默认搜索路径"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                paths = config.get('default_paths', {})
                self.default_paths = {
                    'gpt_path': paths.get('gpt_path', r'H:\GPT-SoVITS-v2-240821\GPT_weights_v2'),
                    'sovits_path': paths.get('sovits_path', r'H:\GPT-SoVITS-v2-240821\SoVITS_weights_v2')
                }
        except Exception as e:
            print(f"加载默认路径配置失败: {str(e)}")
            # 使用默认值
            self.default_paths = {
                'gpt_path': r'H:\GPT-SoVITS-v2-240821\GPT_weights_v2',
                'sovits_path': r'H:\GPT-SoVITS-v2-240821\SoVITS_weights_v2'
            }
    
    def save_default_paths(self):
        """保存默认搜索路径到配置文件"""
        try:
            # 读取现有配置
            config = {}
            if os.path.exists('config.json'):
                with open('config.json', 'r', encoding='utf-8') as f:
                    config = json.load(f)
            
            # 更新默认路径
            config['default_paths'] = self.default_paths
            
            # 保存配置
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            print(f"保存默认路径配置失败: {str(e)}")
            return False
    
    def add_voice_setting(self, role):
        """添加角色音色设置"""
        # 创建角色设置容器
        role_container = QWidget()
        role_layout = QHBoxLayout()
        role_container.setLayout(role_layout)
        
        # 添加角色标签
        role_label = QLabel(f"{role}:")
        role_layout.addWidget(role_label)
        
        # 添加编辑按钮
        edit_btn = QPushButton("编辑音色")
        edit_btn.clicked.connect(lambda: self.show_voice_edit_dialog(role))
        role_layout.addWidget(edit_btn)
        
        # 将整个容器添加到主布局
        self.voice_settings_layout.addWidget(role_container)
        self.voice_settings[role] = edit_btn
        
        # 初始化角色的音色数据
        if role not in self.voice_data:
            self.voice_data[role] = {
                'gpt_path': '',
                'sovits_path': '',
                'ref_audio_path': '',
                'ref_text': ''
            }
    
    def show_default_path_dialog(self):
        """显示默认搜索路径设置对话框"""
        if self.default_path_dialog:
            self.default_path_dialog.close()
        
        self.default_path_dialog = QDialog(self)
        self.default_path_dialog.setWindowTitle("默认搜索路径设置")
        self.default_path_dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout()
        
        # GPT模型路径
        gpt_layout = QHBoxLayout()
        gpt_label = QLabel("GPT模型扫描路径：")
        gpt_path = QLineEdit()
        gpt_path.setText(self.default_paths['gpt_path'])
        gpt_layout.addWidget(gpt_label)
        gpt_layout.addWidget(gpt_path)
        layout.addLayout(gpt_layout)
        
        # Sovits模型路径
        sovits_layout = QHBoxLayout()
        sovits_label = QLabel("Sovits模型扫描路径：")
        sovits_path = QLineEdit()
        sovits_path.setText(self.default_paths['sovits_path'])
        sovits_layout.addWidget(sovits_label)
        sovits_layout.addWidget(sovits_path)
        layout.addLayout(sovits_layout)
        
        # 确定和取消按钮
        button_layout = QHBoxLayout()
        ok_button = QPushButton("确定")
        cancel_button = QPushButton("取消")
        
        def save_paths():
            self.default_paths['gpt_path'] = gpt_path.text()
            self.default_paths['sovits_path'] = sovits_path.text()
            if self.save_default_paths():
                QMessageBox.information(self, "成功", "默认路径设置已保存！")
                self.default_path_dialog.accept()
            else:
                QMessageBox.warning(self, "错误", "保存默认路径设置失败！")
        
        ok_button.clicked.connect(save_paths)
        cancel_button.clicked.connect(self.default_path_dialog.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        self.default_path_dialog.setLayout(layout)
        self.default_path_dialog.show()
    
    def browse_file(self, widget, file_filter="所有文件 (*.*)"):
        """浏览文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文件",
            "",
            file_filter
        )
        if file_path:
            if isinstance(widget, QComboBox):
                widget.setCurrentText(file_path)
            else:
                widget.setText(file_path)
    
    def get_model_files(self, directory, extension):
        """获取指定目录下的模型文件"""
        if not os.path.exists(directory):
            return []
        
        model_files = []
        for file in os.listdir(directory):
            if file.endswith(extension):
                model_files.append(os.path.join(directory, file))
        return sorted(model_files)
    
    def show_voice_edit_dialog(self, role):
        """显示音色编辑对话框"""
        if self.voice_edit_dialog:
            self.voice_edit_dialog.close()
        
        self.voice_edit_dialog = QDialog(self)
        self.voice_edit_dialog.setWindowTitle(f"编辑{role}的音色设置")
        self.voice_edit_dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout()
        
        # GPT模型路径
        gpt_layout = QHBoxLayout()
        gpt_label = QLabel("GPT模型路径：")
        gpt_combo = QComboBox()
        gpt_combo.setEditable(True)
        gpt_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        
        # 添加默认路径下的模型文件
        gpt_files = self.get_model_files(self.default_paths['gpt_path'], '.ckpt')
        gpt_combo.addItems(gpt_files)
        
        # 设置当前值
        current_gpt = self.voice_data[role]['gpt_path']
        if current_gpt:
            index = gpt_combo.findText(current_gpt)
            if index >= 0:
                gpt_combo.setCurrentIndex(index)
            else:
                gpt_combo.setCurrentText(current_gpt)
        
        gpt_browse = QPushButton("浏览")
        gpt_browse.clicked.connect(lambda: self.browse_file(gpt_combo))
        gpt_layout.addWidget(gpt_label)
        gpt_layout.addWidget(gpt_combo)
        gpt_layout.addWidget(gpt_browse)
        layout.addLayout(gpt_layout)
        
        # Sovits模型路径
        sovits_layout = QHBoxLayout()
        sovits_label = QLabel("Sovits模型路径：")
        sovits_combo = QComboBox()
        sovits_combo.setEditable(True)
        sovits_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        
        # 添加默认路径下的模型文件
        sovits_files = self.get_model_files(self.default_paths['sovits_path'], '.pth')
        sovits_combo.addItems(sovits_files)
        
        # 设置当前值
        current_sovits = self.voice_data[role]['sovits_path']
        if current_sovits:
            index = sovits_combo.findText(current_sovits)
            if index >= 0:
                sovits_combo.setCurrentIndex(index)
            else:
                sovits_combo.setCurrentText(current_sovits)
        
        sovits_browse = QPushButton("浏览")
        sovits_browse.clicked.connect(lambda: self.browse_file(sovits_combo))
        sovits_layout.addWidget(sovits_label)
        sovits_layout.addWidget(sovits_combo)
        sovits_layout.addWidget(sovits_browse)
        layout.addLayout(sovits_layout)
        
        # 参考音频路径
        ref_audio_layout = QHBoxLayout()
        ref_audio_label = QLabel("参考音频路径：")
        ref_audio_path = QLineEdit()
        ref_audio_path.setText(self.voice_data[role]['ref_audio_path'])
        ref_audio_browse = QPushButton("浏览")
        ref_audio_browse.clicked.connect(lambda: self.browse_file(ref_audio_path, "音频文件 (*.wav)"))
        ref_audio_layout.addWidget(ref_audio_label)
        ref_audio_layout.addWidget(ref_audio_path)
        ref_audio_layout.addWidget(ref_audio_browse)
        layout.addLayout(ref_audio_layout)
        
        # 参考文本
        ref_text_layout = QVBoxLayout()
        ref_text_label = QLabel("参考文本：")
        ref_text = QTextEdit()
        ref_text.setMaximumHeight(100)
        ref_text.setText(self.voice_data[role]['ref_text'])
        ref_text_layout.addWidget(ref_text_label)
        ref_text_layout.addWidget(ref_text)
        layout.addLayout(ref_text_layout)
        
        # 添加高级参数设置（使用QGroupBox）
        advanced_group = QGroupBox("高级参数设置")
        advanced_group.setCheckable(True)
        advanced_group.setChecked(False)
        advanced_layout = QVBoxLayout()
        
        # 语速控制
        speed_layout = QHBoxLayout()
        speed_label = QLabel("语速：")
        speed_spin = QDoubleSpinBox()
        speed_spin.setRange(0.5, 2.0)
        speed_spin.setSingleStep(0.1)
        speed_spin.setValue(self.voice_data[role].get('speed_factor', 1.0))
        speed_help = QLabel("(控制语音的播放速度，1.0为正常速度)")
        speed_layout.addWidget(speed_label)
        speed_layout.addWidget(speed_spin)
        speed_layout.addWidget(speed_help)
        advanced_layout.addLayout(speed_layout)
        
        # 采样参数
        sampling_layout = QVBoxLayout()
        sampling_label = QLabel("采样参数：")
        advanced_layout.addWidget(sampling_label)
        
        # Top K
        top_k_layout = QHBoxLayout()
        top_k_label = QLabel("Top K：")
        top_k_spin = QSpinBox()
        top_k_spin.setRange(1, 10)
        top_k_spin.setValue(self.voice_data[role].get('top_k', 5))
        top_k_help = QLabel("(控制采样时考虑的候选数量，值越大随机性越强)")
        top_k_layout.addWidget(top_k_label)
        top_k_layout.addWidget(top_k_spin)
        top_k_layout.addWidget(top_k_help)
        advanced_layout.addLayout(top_k_layout)
        
        # Top P
        top_p_layout = QHBoxLayout()
        top_p_label = QLabel("Top P：")
        top_p_spin = QDoubleSpinBox()
        top_p_spin.setRange(0.1, 1.0)
        top_p_spin.setSingleStep(0.1)
        top_p_spin.setValue(self.voice_data[role].get('top_p', 1.0))
        top_p_help = QLabel("(控制采样时的累积概率阈值，值越小输出越保守)")
        top_p_layout.addWidget(top_p_label)
        top_p_layout.addWidget(top_p_spin)
        top_p_layout.addWidget(top_p_help)
        advanced_layout.addLayout(top_p_layout)
        
        # Temperature
        temperature_layout = QHBoxLayout()
        temperature_label = QLabel("Temperature：")
        temperature_spin = QDoubleSpinBox()
        temperature_spin.setRange(0.1, 2.0)
        temperature_spin.setSingleStep(0.1)
        temperature_spin.setValue(self.voice_data[role].get('temperature', 1.0))
        temperature_help = QLabel("(控制采样的随机性，值越大输出越随机)")
        temperature_layout.addWidget(temperature_label)
        temperature_layout.addWidget(temperature_spin)
        temperature_layout.addWidget(temperature_help)
        advanced_layout.addLayout(temperature_layout)
        
        # 重复惩罚
        repetition_layout = QHBoxLayout()
        repetition_label = QLabel("重复惩罚：")
        repetition_spin = QDoubleSpinBox()
        repetition_spin.setRange(1.0, 2.0)
        repetition_spin.setSingleStep(0.05)
        repetition_spin.setValue(self.voice_data[role].get('repetition_penalty', 1.35))
        repetition_help = QLabel("(控制模型避免重复生成相同内容的程度)")
        repetition_layout.addWidget(repetition_label)
        repetition_layout.addWidget(repetition_spin)
        repetition_layout.addWidget(repetition_help)
        advanced_layout.addLayout(repetition_layout)
        
        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)
        
        # 确定和取消按钮
        button_layout = QHBoxLayout()
        ok_button = QPushButton("确定")
        cancel_button = QPushButton("取消")
        
        def save_settings():
            self.voice_data[role] = {
                'gpt_path': gpt_combo.currentText(),
                'sovits_path': sovits_combo.currentText(),
                'ref_audio_path': ref_audio_path.text(),
                'ref_text': ref_text.toPlainText(),
                'speed_factor': speed_spin.value(),
                'top_k': top_k_spin.value(),
                'top_p': top_p_spin.value(),
                'temperature': temperature_spin.value(),
                'repetition_penalty': repetition_spin.value()
            }
            self.voice_edit_dialog.accept()
        
        ok_button.clicked.connect(save_settings)
        cancel_button.clicked.connect(self.voice_edit_dialog.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        self.voice_edit_dialog.setLayout(layout)
        self.voice_edit_dialog.show()
    
    def update_voice_settings(self, dialogues):
        """更新角色音色设置"""
        self.dialogues = dialogues  # 保存分割后的对话
        # 获取所有角色
        roles = set(d['role'] for d in dialogues)
        
        # 清除现有的角色设置（保留旁白）
        while self.voice_settings_layout.count():
            item = self.voice_settings_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.voice_settings.clear()
        
        # 重新添加标题标签
        voice_label = QLabel("角色音色设置")
        self.voice_settings_layout.addWidget(voice_label)
        
        # 重新添加所有角色
        for role in sorted(roles):
            self.add_voice_setting(role)
        
        # 显示角色音色设置
        self.voice_settings_widget.show()
        # 启用生成按钮
        self.generate_btn.setEnabled(True)
    
    def start_split(self):
        if not self.text_edit.toPlainText().strip():
            QMessageBox.warning(self, "警告", "请输入小说文本！")
            return
        
        # 清空日志
        self.log_text.clear()
        
        # 禁用按钮
        self.split_btn.setEnabled(False)
        self.generate_btn.setEnabled(False)
        
        # 创建处理线程
        self.process_thread = NovelProcessThread(
            self.text_edit.toPlainText(),
            self.output_path,
            split_only=True,  # 强制只进行分割
            voice_data=self.voice_data
        )
        self.process_thread.progress.connect(self.update_progress)
        self.process_thread.finished.connect(self.split_finished)
        self.process_thread.log.connect(self.update_log)
        self.process_thread.dialogues_ready.connect(self.update_voice_settings)
        self.process_thread.start()
    
    def select_output_file(self):
        """选择输出文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "选择输出文件",
            "",
            "音频文件 (*.wav)"
        )
        if file_path:
            self.output_path = file_path
            self.log_text.append(f"已选择输出文件: {file_path}")
    
    def start_generate(self):
        """开始生成音频"""
        if not self.dialogues:
            QMessageBox.warning(self, "警告", "请先分割文本！")
            return
            
        if not self.output_path:
            QMessageBox.warning(self, "警告", "请选择输出文件！")
            return
            
        if not self.voice_data:
            QMessageBox.warning(self, "警告", "请先设置角色音色！")
            return
        
        # 设置旁白开关
        self.processor.set_narration(self.narration_checkbox.isChecked())
        
        # 禁用按钮
        self.split_btn.setEnabled(False)
        self.generate_btn.setEnabled(False)
        self.select_output_btn.setEnabled(False)
        self.narration_checkbox.setEnabled(False)
        
        # 创建处理线程
        self.process_thread = NovelProcessThread(
            self.text_edit.toPlainText(),
            self.output_path,
            split_only=False,
            voice_data=self.voice_data
        )
        self.process_thread.dialogues = self.dialogues  # 传递已分割的对话
        self.process_thread.progress.connect(self.update_progress)
        self.process_thread.finished.connect(self.generate_finished)
        self.process_thread.log.connect(self.update_log)
        self.process_thread.start()
    
    def split_finished(self, success, message):
        self.split_btn.setEnabled(True)
        if success:
            QMessageBox.information(self, "完成", message)
        else:
            QMessageBox.warning(self, "错误", message)
    
    def generate_finished(self, success, message):
        # 重新启用按钮
        self.split_btn.setEnabled(True)
        self.generate_btn.setEnabled(True)
        self.select_output_btn.setEnabled(True)
        self.narration_checkbox.setEnabled(True)
        
        if success:
            QMessageBox.information(self, "完成", "音频生成完成！")
        else:
            QMessageBox.warning(self, "错误", f"生成失败: {message}")
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def update_log(self, message):
        self.log_text.append(message)
        # 自动滚动到底部
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    def show_gptsovits_test_dialog(self):
        """显示GPTSoVITS测试对话框"""
        if self.gptsovits_test_dialog:
            self.gptsovits_test_dialog.close()
        
        self.gptsovits_test_dialog = QDialog(self)
        self.gptsovits_test_dialog.setWindowTitle("GPTSoVITS测试面板")
        self.gptsovits_test_dialog.setMinimumWidth(600)
        
        layout = QVBoxLayout()
        
        # GPT模型路径
        gpt_layout = QHBoxLayout()
        gpt_label = QLabel("GPT模型路径：")
        gpt_combo = QComboBox()
        gpt_combo.setEditable(True)
        gpt_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        
        # 添加默认路径下的模型文件
        gpt_files = self.get_model_files(self.default_paths['gpt_path'], '.ckpt')
        gpt_combo.addItems(gpt_files)
        
        gpt_browse = QPushButton("浏览")
        gpt_browse.clicked.connect(lambda: self.browse_file(gpt_combo))
        gpt_layout.addWidget(gpt_label)
        gpt_layout.addWidget(gpt_combo)
        gpt_layout.addWidget(gpt_browse)
        layout.addLayout(gpt_layout)
        
        # Sovits模型路径
        sovits_layout = QHBoxLayout()
        sovits_label = QLabel("Sovits模型路径：")
        sovits_combo = QComboBox()
        sovits_combo.setEditable(True)
        sovits_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        
        # 添加默认路径下的模型文件
        sovits_files = self.get_model_files(self.default_paths['sovits_path'], '.pth')
        sovits_combo.addItems(sovits_files)
        
        sovits_browse = QPushButton("浏览")
        sovits_browse.clicked.connect(lambda: self.browse_file(sovits_combo))
        sovits_layout.addWidget(sovits_label)
        sovits_layout.addWidget(sovits_combo)
        sovits_layout.addWidget(sovits_browse)
        layout.addLayout(sovits_layout)
        
        # 参考音频路径
        ref_audio_layout = QHBoxLayout()
        ref_audio_label = QLabel("参考音频路径：")
        ref_audio_path = QLineEdit()
        ref_audio_browse = QPushButton("浏览")
        ref_audio_browse.clicked.connect(lambda: self.browse_file(ref_audio_path, "音频文件 (*.wav)"))
        ref_audio_layout.addWidget(ref_audio_label)
        ref_audio_layout.addWidget(ref_audio_path)
        ref_audio_layout.addWidget(ref_audio_browse)
        layout.addLayout(ref_audio_layout)
        
        # 参考文本
        ref_text_layout = QVBoxLayout()
        ref_text_label = QLabel("参考文本：")
        ref_text = QTextEdit()
        ref_text.setMaximumHeight(100)
        ref_text_layout.addWidget(ref_text_label)
        ref_text_layout.addWidget(ref_text)
        layout.addLayout(ref_text_layout)
        
        # 合成文本
        synth_text_layout = QVBoxLayout()
        synth_text_label = QLabel("合成文本：")
        synth_text = QTextEdit()
        synth_text.setMaximumHeight(100)
        synth_text_layout.addWidget(synth_text_label)
        synth_text_layout.addWidget(synth_text)
        layout.addLayout(synth_text_layout)
        
        # 合成按钮
        synth_btn = QPushButton("合成")
        synth_btn.clicked.connect(lambda: self.synthesize_text(
            gpt_combo.currentText(),
            sovits_combo.currentText(),
            ref_audio_path.text(),
            ref_text.toPlainText(),
            synth_text.toPlainText()
        ))
        layout.addWidget(synth_btn)
        
        # 状态显示
        self.test_status = QLabel("")
        layout.addWidget(self.test_status)
        
        self.gptsovits_test_dialog.setLayout(layout)
        self.gptsovits_test_dialog.show()
    
    def synthesize_text(self, gpt_path, sovits_path, ref_audio_path, ref_text, synth_text):
        """合成文本"""
        try:
            import requests
            import json
            
            # 设置GPT模型
            response = requests.get(
                f"http://127.0.0.1:9880/set_gpt_weights",
                params={"weights_path": gpt_path}
            )
            if response.status_code != 200:
                self.test_status.setText(f"设置GPT模型失败: {response.text}")
                return
            
            # 设置Sovits模型
            response = requests.get(
                f"http://127.0.0.1:9880/set_sovits_weights",
                params={"weights_path": sovits_path}
            )
            if response.status_code != 200:
                self.test_status.setText(f"设置Sovits模型失败: {response.text}")
                return
            
            # 发送合成请求
            response = requests.post(
                "http://127.0.0.1:9880/tts",
                json={
                    "text": synth_text,
                    "text_lang": "zh",
                    "ref_audio_path": ref_audio_path,
                    "prompt_text": ref_text,
                    "prompt_lang": "zh",
                    "text_split_method": "cut5",
                    "batch_size": 1,
                    "media_type": "wav",
                    "streaming_mode": False
                }
            )
            
            if response.status_code == 200:
                # 保存音频文件
                output_path = "test_output.wav"
                with open(output_path, "wb") as f:
                    f.write(response.content)
                self.test_status.setText(f"合成成功！音频已保存到: {output_path}")
            else:
                self.test_status.setText(f"合成失败: {response.text}")
        
        except Exception as e:
            self.test_status.setText(f"发生错误: {str(e)}")
    
    def show_ai_model_dialog(self):
        """显示AI模型设置对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("大语言模型设置")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # AI对话模型设置组
        chat_group = QGroupBox("AI对话模型设置")
        chat_layout = QVBoxLayout()
        
        chat_api_url_layout = QHBoxLayout()
        chat_api_url_label = QLabel("API地址:")
        self.chat_api_url_input = QLineEdit(self.processor.chat_api_url)
        chat_api_url_layout.addWidget(chat_api_url_label)
        chat_api_url_layout.addWidget(self.chat_api_url_input)
        
        chat_api_key_layout = QHBoxLayout()
        chat_api_key_label = QLabel("API密钥:")
        self.chat_api_key_input = QLineEdit(self.processor.chat_api_key)
        chat_api_key_layout.addWidget(chat_api_key_label)
        chat_api_key_layout.addWidget(self.chat_api_key_input)
        
        chat_model_layout = QHBoxLayout()
        chat_model_label = QLabel("模型名称:")
        self.chat_model_input = QLineEdit(self.processor.chat_model_name)
        chat_model_layout.addWidget(chat_model_label)
        chat_model_layout.addWidget(self.chat_model_input)
        
        chat_layout.addLayout(chat_api_url_layout)
        chat_layout.addLayout(chat_api_key_layout)
        chat_layout.addLayout(chat_model_layout)
        chat_group.setLayout(chat_layout)
        
        # AI对话分割模型设置组
        split_group = QGroupBox("AI对话分割模型设置")
        split_layout = QVBoxLayout()
        
        split_api_url_layout = QHBoxLayout()
        split_api_url_label = QLabel("API地址:")
        self.split_api_url_input = QLineEdit(self.processor.api_url)
        split_api_url_layout.addWidget(split_api_url_label)
        split_api_url_layout.addWidget(self.split_api_url_input)
        
        split_api_key_layout = QHBoxLayout()
        split_api_key_label = QLabel("API密钥:")
        self.split_api_key_input = QLineEdit(self.processor.api_key)
        split_api_key_layout.addWidget(split_api_key_label)
        split_api_key_layout.addWidget(self.split_api_key_input)
        
        split_model_layout = QHBoxLayout()
        split_model_label = QLabel("模型名称:")
        self.split_model_input = QLineEdit(self.processor.model_name)
        split_model_layout.addWidget(split_model_label)
        split_model_layout.addWidget(self.split_model_input)
        
        split_layout.addLayout(split_api_url_layout)
        split_layout.addLayout(split_api_key_layout)
        split_layout.addLayout(split_model_layout)
        split_group.setLayout(split_layout)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        cancel_btn = QPushButton("取消")
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        
        # 添加所有组件到主布局
        layout.addWidget(chat_group)
        layout.addWidget(split_group)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        
        def save_settings():
            success = self.processor.update_config(
                self.split_api_url_input.text(),
                self.split_api_key_input.text(),
                self.split_model_input.text(),
                self.chat_api_url_input.text(),
                self.chat_api_key_input.text(),
                self.chat_model_input.text()
            )
            if success:
                QMessageBox.information(dialog, "成功", "设置已保存")
                dialog.accept()
            else:
                QMessageBox.warning(dialog, "错误", "保存设置失败")
        
        save_btn.clicked.connect(save_settings)
        cancel_btn.clicked.connect(dialog.reject)
        
        dialog.exec()

    def setup_ai_chat_area(self):
        """设置AI对话区域"""
        ai_group = QGroupBox("AI助手")
        ai_layout = QVBoxLayout()
        
        # 添加按钮区域
        button_layout = QHBoxLayout()
        self.reset_chat_btn = QPushButton("重置对话")
        self.stop_chat_btn = QPushButton("停止生成")
        self.stop_chat_btn.setEnabled(False)  # 初始状态禁用
        
        button_layout.addWidget(self.reset_chat_btn)
        button_layout.addWidget(self.stop_chat_btn)
        button_layout.addStretch()
        
        # 连接按钮信号
        self.reset_chat_btn.clicked.connect(self.reset_chat)
        self.stop_chat_btn.clicked.connect(self.stop_chat)
        
        # 聊天历史记录
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setMinimumHeight(200)
        
        # 输入区域
        input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("输入问题，按回车发送...")
        self.chat_input.returnPressed.connect(self.send_chat_message)
        
        # 添加发送按钮
        self.send_btn = QPushButton("发送")
        self.send_btn.clicked.connect(self.send_chat_message)
        
        input_layout.addWidget(self.chat_input)
        input_layout.addWidget(self.send_btn)
        
        # 添加所有组件到主布局
        ai_layout.addLayout(button_layout)
        ai_layout.addWidget(self.chat_history)
        ai_layout.addLayout(input_layout)
        
        ai_group.setLayout(ai_layout)
        return ai_group

    def reset_chat(self):
        """重置对话"""
        # 停止正在进行的AI对话
        if self.chat_thread and self.chat_thread.isRunning():
            self.chat_thread.terminate()
            self.chat_thread.wait()
            self.chat_thread = None
        
        # 清空对话历史
        self.processor.clear_chat_history()
        
        # 清空聊天历史
        self.chat_history.clear()
        # 清空输入框
        self.chat_input.clear()
        # 重置输入框状态
        self.chat_input.setEnabled(True)
        self.chat_input.setPlaceholderText("输入问题，按回车发送...")
        self.chat_input.setFocus()
        # 重置按钮状态
        self.send_btn.setEnabled(True)
        self.stop_chat_btn.setEnabled(False)
        # 重置聊天状态
        self.is_chatting = False
    
    def stop_chat(self):
        """停止AI对话"""
        if self.chat_thread and self.chat_thread.isRunning():
            self.chat_thread.terminate()
            self.chat_thread.wait()
            self.is_chatting = False
            self.stop_chat_btn.setEnabled(False)
            self.chat_input.setEnabled(True)
            self.chat_input.setPlaceholderText("输入问题，按回车发送...")
            self.chat_input.setFocus()
    
    def send_chat_message(self):
        """发送消息到AI助手"""
        if self.is_chatting:  # 如果正在对话中，不发送新消息
            return
            
        message = self.chat_input.text().strip()
        if not message:
            return
            
        # 显示用户消息
        self.chat_history.append(f"你: {message}")
        
        # 清空输入框
        self.chat_input.clear()
        
        # 禁用输入框和发送按钮
        self.chat_input.setEnabled(False)
        self.chat_input.setPlaceholderText("正在等待AI回复...")
        
        # 添加AI前缀
        self.chat_history.append("AI: ")
        
        # 设置状态
        self.is_chatting = True
        self.stop_chat_btn.setEnabled(True)
        
        # 创建并启动AI对话线程
        self.chat_thread = AIChatThread(self.processor, message)
        self.chat_thread.token.connect(self.handle_ai_token)
        self.chat_thread.finished.connect(self.handle_ai_finished)
        self.chat_thread.error.connect(self.handle_ai_error)
        self.chat_thread.start()
    
    def handle_ai_token(self, token):
        """处理AI的单个token"""
        # 获取最后一个文本块
        cursor = self.chat_history.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        
        # 插入token
        cursor.insertText(token)
        
        # 滚动到底部
        self.chat_history.verticalScrollBar().setValue(
            self.chat_history.verticalScrollBar().maximum()
        )
        
        # 强制更新界面
        QApplication.processEvents()
    
    def handle_ai_finished(self, response):
        """处理AI回复完成"""
        self.is_chatting = False
        self.stop_chat_btn.setEnabled(False)
        self.chat_input.setEnabled(True)
        self.chat_input.setPlaceholderText("输入问题，按回车发送...")
        self.chat_input.setFocus()
        
        # 滚动到底部
        self.chat_history.verticalScrollBar().setValue(
            self.chat_history.verticalScrollBar().maximum()
        )
    
    def handle_ai_error(self, error_msg):
        """处理AI错误"""
        self.is_chatting = False
        self.stop_chat_btn.setEnabled(False)
        self.chat_history.append(f"AI: 抱歉，我现在遇到了一些问题：{error_msg}")
        self.chat_input.setEnabled(True)
        self.chat_input.setPlaceholderText("输入问题，按回车发送...")
        self.chat_input.setFocus()
        
        # 滚动到底部
        self.chat_history.verticalScrollBar().setValue(
            self.chat_history.verticalScrollBar().maximum()
        )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 
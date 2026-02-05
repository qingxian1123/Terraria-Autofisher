import soundcard as sc
import numpy as np
import pyautogui
import time
import threading
import tkinter as tk
from tkinter import ttk
from scipy.io import wavfile
import os 

class FishingBot:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Terraria 钓鱼助手")
        self.root.geometry("500x750")
        self.root.resizable(True, True)
        self.root.configure(bg='#2b1f35')
        
        # 状态变量
        self.is_running = False
        self.similarity_threshold = 0.7
        self.cooldown_time = 2.0
        self.fish_count = 0
        self.last_action_time = 0
        self.mic = None
        self.template_audio = None
        self.template_samplerate = None
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(current_dir, "assets", "splash_template.wav")
        
        try:
            if not os.path.exists(template_path):
                raise FileNotFoundError(f"找不到音频文件: {template_path}")

            self.template_samplerate, template_data = wavfile.read(template_path)
            
            # 转换为单声道 (如果是双声道)
            if len(template_data.shape) > 1:
                template_data = np.mean(template_data, axis=1)
            
            # 归一化处理
            template_data = template_data.astype(np.float32)
            max_abs = np.max(np.abs(template_data))
            if max_abs > 0:
                template_data /= max_abs
                
            self.template_audio = template_data
            print(f"✅ 成功加载素材: {template_path}")
            print(f"采样率: {self.template_samplerate}, 长度: {len(self.template_audio)}")
            
        except Exception as e:
            print(f"❌ 加载音频失败: {e}")
            self.template_audio = None
        
        self.create_widgets()
        
    def create_widgets(self):
        # ===== 标题 =====
        title = tk.Label(self.root, text="TERRARIA 钓鱼助手",
                         font=('Courier New', 18, 'bold'), bg='#4a3556', fg='#87ceeb', pady=20)
        title.pack(fill='x', padx=10, pady=(15, 10))
        
        main_frame = tk.Frame(self.root, bg='#2b1f35')
        main_frame.pack(padx=15, pady=10, fill='both', expand=True)
        
        # ===== 相似度阈值 =====
        threshold_box = tk.LabelFrame(main_frame, text=" 🎣 相似度阈值 ", font=('Courier New', 10, 'bold'),
                                      bg='#3d2d4f', fg='#f0e68c', bd=3)
        threshold_box.pack(fill='x', pady=10)
        self.threshold_var = tk.DoubleVar(value=0.7)
        tk.Scale(threshold_box, from_=0.5, to=0.95, resolution=0.01, orient='horizontal',
                 variable=self.threshold_var, font=('Courier New', 9), bg='#4a3556', fg='#ffffff',
                 troughcolor='#2b1f35', length=400).pack(padx=10, pady=10)
        
        # ===== 冷却时间 =====
        cooldown_box = tk.LabelFrame(main_frame, text=" ⏱ 冷却时间(秒) ", font=('Courier New', 10, 'bold'),
                                     bg='#3d2d4f', fg='#f0e68c', bd=3)
        cooldown_box.pack(fill='x', pady=10)
        self.cooldown_var = tk.DoubleVar(value=2.0)
        tk.Scale(cooldown_box, from_=1.0, to=5.0, resolution=0.1, orient='horizontal',
                 variable=self.cooldown_var, font=('Courier New', 9), bg='#4a3556', fg='#ffffff',
                 troughcolor='#2b1f35', length=400).pack(padx=10, pady=10)
        
        # ===== 状态显示 =====
        status_box = tk.LabelFrame(main_frame, text=" 📊 实时状态 ", font=('Courier New', 10, 'bold'),
                                   bg='#3d2d4f', fg='#f0e68c', bd=3)
        status_box.pack(fill='x', pady=10)
        
        self.volume_bar = ttk.Progressbar(status_box, length=400, mode='determinate', maximum=100)
        self.volume_bar.pack(padx=10, pady=10)
        
        self.status_text = tk.Label(status_box, text="⚡ 状态: 待命中", font=('Courier New', 10),
                                    bg='#3d2d4f', fg='#ffa500', anchor='w')
        self.status_text.pack(fill='x', padx=10, pady=5)
        
        self.fish_label = tk.Label(status_box, text="🐟 钓鱼次数: 0", font=('Courier New', 13, 'bold'),
                                   bg='#3d2d4f', fg='#00ffff', anchor='w')
        self.fish_label.pack(fill='x', padx=10, pady=5)
        
        # ===== 按钮区域 =====
        btn_frame = tk.Frame(main_frame, bg='#2b1f35')
        btn_frame.pack(pady=30)
        
        self.start_btn = tk.Button(btn_frame, text="▶ 开始钓鱼", font=('Courier New', 14, 'bold'),
                                   bg='#228b22', fg='#ffffff', activebackground='#32cd32',
                                   width=15, height=2, bd=4, relief='raised', command=self.toggle_start)
        self.start_btn.grid(row=0, column=0, padx=15)
        
        tk.Button(btn_frame, text="🔄 重置", font=('Courier New', 11), bg='#4a3556', fg='#ffffff',
                  activebackground='#5a4566', width=10, height=2, bd=3, relief='raised',
                  command=self.reset).grid(row=0, column=1, padx=15)
        
    def get_loopback(self):
        try:
            mics = sc.all_microphones(include_loopback=True)
            speaker_name = sc.default_speaker().name
            for mic in mics:
                if speaker_name in mic.name or "Loopback" in mic.name:
                    return mic
            return sc.default_microphone()
        except:
            return None
    
    def click_mouse(self):
        pyautogui.mouseDown()
        time.sleep(0.05)
        pyautogui.mouseUp()
    
    def calculate_similarity(self, data, template):
        if data.shape != template.shape:
            if len(data) < len(template):
                data, template = template, data
            corr = np.correlate(data, template, mode='valid')
            max_corr = np.max(corr)
            norm = np.sqrt(np.sum(data**2) * np.sum(template**2))
            return 0.0 if norm == 0 else max_corr / norm
        else:
            return np.corrcoef(data, template)[0, 1] if not np.isnan(np.corrcoef(data, template)[0, 1]) else 0.0
    
    def fishing_thread(self):
        if self.template_audio is None:
            self.root.after(0, lambda: self.status_text.config(text="❌ 缺少 assets/splash_template.wav", fg='#ff0000'))
            self.is_running = False
            return
        
        self.mic = self.get_loopback()
        if not self.mic:
            self.root.after(0, lambda: self.status_text.config(text="❌ 未找到音频设备", fg='#ff0000'))
            self.is_running = False
            return
        
        time.sleep(1)
        self.click_mouse()
        self.last_action_time = time.time()
        
        with self.mic.recorder(samplerate=44100) as recorder:
            while self.is_running:
                numframes = len(self.template_audio) * 2
                data = recorder.record(numframes=numframes)
                
                self.similarity_threshold = self.threshold_var.get()
                self.cooldown_time = self.cooldown_var.get()
                
                if time.time() - self.last_action_time < self.cooldown_time:
                    continue
                
                if data.ndim > 1:
                    data_mono = np.mean(data, axis=1)
                else:
                    data_mono = data.flatten()
                
                max_val = np.max(np.abs(data_mono))
                if max_val > 0:
                    data_mono = data_mono / (max_val + 1e-10)
                
                volume = np.mean(np.abs(data_mono))
                if volume < 0.01:
                    similarity = 0.0
                else:
                    similarity = self.calculate_similarity(data_mono, self.template_audio)
                
                self.root.after(0, self.update_display, similarity)
                
                if similarity > self.similarity_threshold:
                    self.fish_count += 1
                    self.root.after(0, self.on_catch, similarity)
                    self.click_mouse()
                    time.sleep(0.5)
                    self.click_mouse()
                    self.last_action_time = time.time()
                    recorder.flush()
    
    def update_display(self, similarity):
        progress = min(100, max(0, (similarity / self.similarity_threshold) * 100))
        self.volume_bar['value'] = progress
    
    def on_catch(self, similarity):
        self.status_text.config(text="🎉 上钩！", fg='#00ff00')
        self.fish_label.config(text=f"🐟 钓鱼次数: {self.fish_count}")
        self.root.after(800, lambda: self.status_text.config(text="⚡ 监听中...", fg='#87ceeb'))
    
    def toggle_start(self):
        if not self.is_running:
            self.is_running = True
            self.start_btn.config(text="⏸ 停止钓鱼", bg='#dc143c', activebackground='#ff4500')
            self.status_text.config(text="⚡ 监听中...", fg='#87ceeb')
            threading.Thread(target=self.fishing_thread, daemon=True).start()
        else:
            self.is_running = False
            self.start_btn.config(text="▶ 开始钓鱼", bg='#228b22', activebackground='#32cd32')
            self.status_text.config(text="⚡ 已停止", fg='#ffa500')
    
    def reset(self):
        self.fish_count = 0
        self.fish_label.config(text="🐟 钓鱼次数: 0")
        self.status_text.config(text="✅ 已重置", fg='#98fb98')
        self.root.after(1500, lambda: self.status_text.config(text="⚡ 状态: 待命中", fg='#ffa500'))
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = FishingBot()
    app.run()
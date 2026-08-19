import cv2
import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk
import os

# Configure appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class RobotScreenApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("AURA Robot Screen Controller")
        self.geometry("1024x600")
        
        # Expression video mapping
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.expressions = {
            "Idle": os.path.join(base_dir, "idle.MP4"),
            "Charging": os.path.join(base_dir, "charging.MP4"),
            "Low Battery": os.path.join(base_dir, "lowbattery.MOV"),
            "Navigation": os.path.join(base_dir, "navigation.mp4"),
            "Task Successful": os.path.join(base_dir, "task successful.MOV"),
            "Task Failed": os.path.join(base_dir, "taskfailed.MP4")
        }
        
        # Setup UI
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar for buttons
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(len(self.expressions) + 1, weight=1)
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="AURA Expressions", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 20))
        
        # Video view
        self.video_frame = ctk.CTkFrame(self, fg_color="black")
        self.video_frame.grid(row=0, column=1, sticky="nsew")
        
        # Use standard tk.Label for faster image updates
        self.video_label = tk.Label(self.video_frame, bg="black", borderwidth=0)
        self.video_label.pack(expand=True, fill="both")
        
        self.current_video = None
        self.cap = None
        self.playing = False
        self.after_id = None
        self.tk_img = None  # keep reference
        
        # Create buttons
        row = 1
        self.buttons = {}
        for name in self.expressions.keys():
            btn = ctk.CTkButton(self.sidebar, text=name, 
                                command=lambda n=name: self.play_expression(n),
                                height=40, font=ctk.CTkFont(size=14))
            btn.grid(row=row, column=0, padx=20, pady=10, sticky="ew")
            self.buttons[name] = btn
            row += 1
            
        # Fullscreen toggle
        self.fullscreen_btn = ctk.CTkButton(self.sidebar, text="Toggle Fullscreen", 
                                            command=self.toggle_fullscreen, 
                                            fg_color="transparent", border_width=2, 
                                            text_color=("gray10", "#DCE4EE"))
        self.fullscreen_btn.grid(row=row+1, column=0, padx=20, pady=20, sticky="s")
        
        self.is_fullscreen = False
        
        # Start default expression
        self.play_expression("Idle")
        
    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)
        if not self.is_fullscreen:
            self.geometry("1024x600")
            
    def play_expression(self, name):
        # Update button colors to indicate active expression
        for btn_name, btn in self.buttons.items():
            if btn_name == name:
                btn.configure(fg_color="#2FA572", hover_color="#106A43") # Green for active
            else:
                btn.configure(fg_color=["#3a7ebf", "#1f538d"], hover_color=["#325882", "#14375e"]) # Default blue
                
        video_path = self.expressions.get(name)
        if not video_path or not os.path.exists(video_path):
            print(f"Cannot play {name}, file missing at {video_path}")
            self.video_label.configure(text=f"Video not found:\n{name}", image="")
            return
            
        self.video_label.configure(text="")
        
        self.playing = False
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
            
        if self.cap:
            self.cap.release()
            
        self.current_video = video_path
        self.cap = cv2.VideoCapture(video_path)
        
        # Read FPS to sync playback roughly
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0: fps = 30
        
        # Reduce delay slightly to account for processing overhead
        self.frame_delay = max(1, int(1000 / fps) - 5)
        
        self.playing = True
        self.update_frame()
        
    def update_frame(self):
        if not self.playing or not self.cap:
            return
            
        ret, frame = self.cap.read()
        if not ret:
            # Loop video
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            
        if ret:
            # Resize while keeping aspect ratio before color conversion to save CPU
            label_w = self.video_label.winfo_width()
            label_h = self.video_label.winfo_height()
            
            if label_w > 10 and label_h > 10:
                h, w, _ = frame.shape
                scale = min(label_w/w, label_h/h)
                new_w, new_h = int(w * scale), int(h * scale)
                if new_w > 0 and new_h > 0 and (new_w != w or new_h != h):
                    frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            
            # Convert color from BGR to RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            img = Image.fromarray(frame)
            self.tk_img = ImageTk.PhotoImage(image=img)
            self.video_label.configure(image=self.tk_img)
            
        # Schedule next frame
        self.after_id = self.after(self.frame_delay, self.update_frame)

    def on_closing(self):
        self.playing = False
        if self.cap:
            self.cap.release()
        self.destroy()

if __name__ == "__main__":
    app = RobotScreenApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    # Allow pressing Escape to exit fullscreen or quit
    app.bind("<Escape>", lambda event: app.attributes("-fullscreen", False) if app.attributes("-fullscreen") else app.on_closing())
    app.mainloop()

Here is the comprehensive Product Requirement Document (PRD) and Technical Specification sheet for your CECT Hindi/English Typing Application. You can hand this directly to your developer, as it contains all the system logic, font frameworks, evaluation criteria, and a baseline source script they need to build the software.📑 Product Requirement Document (PRD)Project Name: CECT/CPCT Bilingual Typing Examination Simulator1. Project OverviewThe objective is to build a standalone desktop application to prepare candidates for the Computer Proficiency Certification Test (CPCT / CECT) conducted under official government structures (such as TCS iON platforms). The application must perfectly simulate the strict conditions of the actual government exam room, emphasizing specific keyboard font layouts and evaluation scoring systems.2. Core Functional RequirementsA. Dual Language ArchitectureEnglish Module: Standard typing drills tracking words and symbols.Hindi Module: Built strictly around the Mangal Unicode Font. It must support native configuration mappings for:Remington (GAIL) LayoutInScript LayoutB. Exam Mode Rules (Strict Simulation)Timer System: Fixed countdown timer setting of 15 Minutes (900 Seconds) for official full-length tests, with customizable 1, 2, and 5-minute practice intervals.TCS iON Screen Layout: A vertical split-screen design. The top container displays the static source text passage, and the bottom text window takes the user's keystroke entries.Keystroke Restraints: An admin configuration toggle to Enable or Completely Lock the Backspace Key (reflecting different government tier rules).No Real-time Feedback: During Exam Mode, errors must not turn red instantly. The user should see plain text entry just like the real exam, with full evaluation calculated only after hitting the "Submit" button.C. Official CECT Marking FormulaDevelopers must use the official Indian Government evaluation calculation:Standard Word Definition: Exactly 5 Keystrokes (including spaces) = 1 Word.Gross Words Per Minute (GWPM): \(\frac{\text{Total Keystrokes Entered}}{5} \div \text{Time Elapsed (Minutes)}\)Net Words Per Minute (NWPM): \(\frac{\text{Correct Keystrokes Entered}}{5} \div \text{Time Elapsed (Minutes)}\)Accuracy Percentage: \(\frac{\text{Correct Keystrokes}}{\text{Total Keystrokes Entered}} \times 100\)Passing Benchmark: Minimum 20 Net WPM with at least 85% Accuracy on Hindi modules.3. Technical Stack RecommendationLanguage: Python 3.10+GUI Library: customtkinter (for modern appearance styles) or PyQt6 (for enterprise scalability).Packaging Tool: PyInstaller (To pack the project files into a portable .exe standalone application for Windows environments).4. Prototype Architecture ScriptProvide this boilerplate code to your developer. It sets up the UI environment, implements the layout, handles Unicode text tracking, and applies the official 5-Keystroke math rules automatically.pythonimport tkinter as tk
import customtkinter as ctk
import time

ctk.set_appearance_mode("Light") 
ctk.set_default_color_theme("blue")

class CECTTypingApplication(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("CECT / CPCT Official Hindi Typing Examination Simulator")
        self.geometry("1000x650")
        self.minsize(950, 600)
        
        # Reference Hindi Test Paragraphs (Mangal Font Specifications)
        self.exam_passages = [
            "सफलता नियमित अभ्यास और कठिन परिश्रम से ही संभव है। परीक्षा कक्ष में बैठते समय अपने मन को शांत रखना अत्यंत आवश्यक है। जब आप कीबोर्ड पर अपनी उंगलियों को सही स्थिति में रखते हैं, तो आपकी गति और सटीकता दोनों में निरंतर सुधार होता है। भारत एक विशाल और विविध संस्कृतियों वाला देश है जहाँ प्रत्येक राज्य की अपनी विशिष्ट पहचान और भाषा है।",
            "कंप्यूटर दक्षता प्रमाणीकरण परीक्षा एक महत्वपूर्ण माध्यम है जिसके द्वारा विभिन्न सरकारी विभागों में डाटा एंट्री ऑपरेटर और सहायक ग्रेड तीन के पदों पर योग्य उम्मीदवारों का चयन किया जाता है। परीक्षा के दौरान बैकस्पेस कुंजी का उपयोग सीमित या वर्जित हो सकता है, इसलिए शुद्धता पर ध्यान देना आवश्यक है।"
        ]
        
        self.current_text = self.exam_passages[0]
        self.time_left = 900  # 15 Minutes Standard Exam Limit
        self.timer_running = False
        self.start_time = None
        self.allow_backspace = True  # Toggle configuration parameter
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self.build_top_bar()
        self.build_exam_interface()
        self.load_exam_passage()

    def build_top_bar(self):
        self.top_bar = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color="#1e3a8a")
        self.top_bar.grid(row=0, column=0, sticky="ew")
        self.top_bar.grid_propagate(False)
        
        title_lbl = ctk.CTkLabel(
            self.top_bar, text="CECT HINDI TYPING SIMULATOR (MANGAL FONT SYSTEM)", 
            font=ctk.CTkFont(size=16, weight="bold"), text_color="white"
        )
        title_lbl.pack(side="left", padx=20, pady=15)
        
        self.timer_lbl = ctk.CTkLabel(
            self.top_bar, text="Time Remaining: 15:00", 
            font=ctk.CTkFont(size=16, weight="bold"), text_color="#facc15"
        )
        self.timer_lbl.pack(side="right", padx=20, pady=15)

    def build_exam_interface(self):
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=1, column=0, padx=20, pady=20, sticky="nsew")
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure((1, 3), weight=1)
        
        # UI Instruction Notice Panel
        layout_info = ctk.CTkLabel(
            self.main_container, 
            text="⚠️ EXAMINATION ENVIRONMENT: Ensure native OS language input is set to Hindi Remington (GAIL) or InScript.",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#b91c1c"
        )
        layout_info.grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        # Top Box - Text Source Prompt Screen
        self.source_view = tk.Text(
            self.main_container, wrap="word", font=("Mangal", 15), 
            bg="#f8fafc", fg="#1e293b", relief="solid", bd=1, padx=15, pady=15
        )
        self.source_view.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        
        middle_bar = ctk.CTkLabel(
            self.main_container, text="Response Input Area:", font=ctk.CTkFont(size=13, weight="semibold")
        )
        middle_bar.grid(row=2, column=0, sticky="w", pady=5)
        
        # Bottom Box - User Entry Pad
        self.input_box = ctk.CTkTextbox(self.main_container, font=("Mangal", 15), border_width=1, corner_radius=0)
        self.input_box.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        self.input_box.bind("<KeyRelease>", self.track_keystrokes)
        self.input_box.bind("<BackSpace>", self.intercept_backspace)
        
        # Bottom Action Control Bar
        self.action_panel = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.action_panel.grid(row=4, column=0, sticky="ew", pady=5)
        
        self.restart_btn = ctk.CTkButton(self.action_panel, text="Reset Exam", fg_color="#475569", command=self.reset_exam)
        self.restart_btn.pack(side="left")
        
        self.submit_btn = ctk.CTkButton(self.action_panel, text="Submit Sheet", fg_color="#16a34a", command=self.calculate_final_cect_metrics)
        self.submit_btn.pack(side="right")

    def load_exam_passage(self):
        self.source_view.config(state="normal")
        self.source_view.delete("1.0", tk.END)
        self.source_view.insert("1.0", self.current_text)
        self.source_view.config(state="disabled")

    def intercept_backspace(self, event):
        if not self.allow_backspace:
            return "break" # Aborts the backspace execution loop dynamically

    def track_keystrokes(self, event):
        typed_string = self.input_box.get("1.0", "end-1c")
        if not self.timer_running and len(typed_string) > 0:
            self.timer_running = True
            self.start_time = time.time()
            self.countdown_loop()

    def countdown_loop(self):
        if self.timer_running and self.time_left > 0:
            self.time_left -= 1
            mins, secs = divmod(self.time_left, 60)
            self.timer_lbl.configure(text=f"Time Remaining: {mins:02d}:{secs:02d}")
            self.after(1000, self.countdown_loop)
        elif self.time_left <= 0:
            self.calculate_final_cect_metrics()

    def calculate_final_cect_metrics(self):
        self.timer_running = False
        self.input_box.configure(state="disabled")
        
        typed_content = self.input_box.get("1.0", "end-1c")
        time_elapsed_mins = max((time.time() - self.start_time) / 60, 0.1) if self.start_time else 0.1
        
        total_keystrokes = len(typed_content)
        correct_chars = sum(1 for i, char in enumerate(typed_content) if i < len(self.current_text) and char == self.current_text[i])
                
        # Indian Government standard typing evaluation math models
        gross_wpm = round((total_keystrokes / 5) / time_elapsed_mins, 2)
        net_wpm = round((correct_chars / 5) / time_elapsed_mins, 2)
        accuracy = round((correct_chars / total_keystrokes * 100), 2) if total_keystrokes > 0 else 0.0
        
        status = "PASSED (QUALIFIED) ✅" if net_wpm >= 20.0 and accuracy >= 85.0 else "FAILED (NOT QUALIFIED) ❌"
        
        self.display_scorecard(status, gross_wpm, net_wpm, total_keystrokes, accuracy)

    def display_scorecard(self, status, gwpm, nwpm, keys, acc):
        score_win = ctk.CTkToplevel(self)
        score_win.title("Official Examination Scorecard")
        score_win.geometry("460x320")
        
        report_text = (
            f"=== CECT EVALUATION REPORT ===\n\n"
            f"Exam Status: {status}\n"
            f"Gross Speed: {gwpm} WPM\n"
            f"Net Speed Score: {nwpm} NWPM\n"
            f"Total Keystrokes: {keys}\n"
            f"Accuracy Margin: {acc}%\n\n"
            f"*Metric Note: Passing requires min 20 NWPM and 85% accuracy."
        )
        lbl = ctk.CTkLabel(score_win, text=report_text, font=ctk.CTkFont(size=14), justify="left")
        lbl.pack(padx=25, pady=25)

    def reset_exam(self):
        self.timer_running = False
        self.start_time = None
        self.time_left = 900
        self.timer_lbl.configure(text="Time Remaining: 15:00")
        self.input_box.configure(state="normal")
        self.input_box.delete("1.0", tk.END)
        self.load_exam_passage()

if __name__ == "__main__":
    app = CECTTypingApplication()
    app.mainloop()
from uu import Error
import customtkinter as ctk
import pyperclip
import keyboard
import time
import requests
import threading
from pystray import MenuItem as item, Icon
from PIL import Image, ImageDraw
import os
import json
from tkinter import messagebox
from cryptography.fernet import Fernet
import threading

# Add this near the top of your file, after the imports
AVAILABLE_MODELS = [
    "deepseek/deepseek-chat",
    "anthropic/claude-3.5-sonnet",
    "openai/chatgpt-latest",
    "openai/gpt-4o-mini",
    "google/gemini-flash-1.5",
    "deepseek/deepseek-r1",
    'custom'
]

DEFAULT_MODEL = "deepseek/deepseek-chat"

# Add configuration management
CONFIG_FILE = "clippy_config.json"
KEY_FILE = ".clippy_key"

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

# System tray icon setup
tray_icon = None

def show_toast(message, is_error=False):
    toast = ctk.CTkToplevel()
    toast.overrideredirect(True)  # Remove window decorations
    toast.attributes('-topmost', True)
    
    # Set color based on message type
    bg_color = "#FF5555" if is_error else "#55AA55"
    
    # Create label with padding and color
    label = ctk.CTkLabel(
        toast,
        text=message,
        fg_color=bg_color,
        corner_radius=8,
        padx=20,
        pady=10
    )
    label.pack(padx=10, pady=10)
    
    # Position at bottom right
    screen_width = toast.winfo_screenwidth()
    screen_height = toast.winfo_screenheight()
    toast_width = 300  # Assuming a fixed width for the toast
    toast_height = 100  # Assuming a fixed height for the toast
    x = (screen_width // 2) - (toast_width // 2)
    y = (screen_height // 2) - (toast_height // 2)
    toast.geometry(f"{toast_width}x{toast_height}+{x}+{y}")
    
    # Auto-close after 3 seconds
    toast.after(3000, toast.destroy)

# Generate or load encryption key
def get_encryption_key():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as key_file:
            return key_file.read()
    
    key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as key_file:
        key_file.write(key)
    os.chmod(KEY_FILE, 0o600)  # Secure permissions on key file
    return key

def load_config():
    """Load configuration with encrypted token and model selection"""
    if not os.path.exists(CONFIG_FILE):
        return {"api_token": None, "model": DEFAULT_MODEL}
    
    try:    
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        
        # Only decrypt the token if it exists
        if config.get("encrypted_token"):
            cipher_suite = Fernet(get_encryption_key())
            decrypted_token = cipher_suite.decrypt(config["encrypted_token"].encode())
            config["api_token"] = decrypted_token.decode()
            del config["encrypted_token"]
        
        # Ensure model is set, use default if not present
        if "model" not in config:
            config["model"] = DEFAULT_MODEL
            
        return config
        
    except Exception as e:
        show_toast(f"Security error: {str(e)}", is_error=True)
        return {"api_token": None, "model": DEFAULT_MODEL}

def save_config(token, model=None, shortcut=None):
    """Save configuration with encrypted token, model selection, and shortcut"""
    try:
        # Load existing config to preserve model and shortcut if not changing
        existing_config = load_config()
        
        cipher_suite = Fernet(get_encryption_key())
        encrypted_token = cipher_suite.encrypt(token.encode())
        
        config = {
            "encrypted_token": encrypted_token.decode(),
            "model": model if model else existing_config.get("model", DEFAULT_MODEL),
            "shortcut": shortcut if shortcut else existing_config.get("shortcut", "ctrl+shift+'")
        }
        
        # Save with secure permissions using atomic write
        with open(CONFIG_FILE + ".tmp", "w") as f:
            json.dump(config, f)
        
        os.replace(CONFIG_FILE + ".tmp", CONFIG_FILE)
        os.chmod(CONFIG_FILE, 0o600)  # Set secure permissions
        
    except Exception as e:
        show_toast(f"Failed to save config: {str(e)}", is_error=True)

def show_model_dialog():
    """Show model and shortcut selection dialog using customtkinter"""
    dialog = ctk.CTkToplevel()
    dialog.title("AI Model and Shortcut Configuration")
    dialog.geometry("400x500")
    dialog.attributes('-topmost', True)
    
    label = ctk.CTkLabel(dialog, text="Select AI Model:", wraplength=350)
    label.pack(pady=10)
    
    # Get current config
    current_config = load_config()
    current_model = current_config.get("model", DEFAULT_MODEL)
    
    # Create variable for radio buttons
    selected_model = ctk.StringVar(value=current_model)
    
    # Create a frame to contain all model-related widgets
    models_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    models_frame.pack(fill="x", padx=20)
    
    # Create radio buttons for each model
    for model in AVAILABLE_MODELS:
        radio = ctk.CTkRadioButton(
            models_frame,
            text="Custom Model" if model == "custom" else model,
            variable=selected_model,
            value=model,
            command=lambda: on_model_selection()
        )
        radio.pack(pady=5, anchor="w")
    
    # Create frame for custom model input right after the models list
    custom_frame = ctk.CTkFrame(models_frame)
    custom_frame.pack(pady=5)
    custom_frame.pack_forget()  # Hide initially
    
    custom_label = ctk.CTkLabel(custom_frame, text="Enter custom model:")
    custom_label.pack(side="left", padx=5)
    custom_model_entry = ctk.CTkEntry(custom_frame, width=200)
    custom_model_entry.pack(side="left", padx=5)
    
    def on_model_selection():
        if selected_model.get() == "custom":
            custom_frame.pack(pady=5)
            if current_model not in AVAILABLE_MODELS:
                custom_model_entry.delete(0, 'end')
                custom_model_entry.insert(0, current_model)
        else:
            custom_frame.pack_forget()
    
    # If current model is custom, select custom radio and show entry
    if current_model not in AVAILABLE_MODELS:
        selected_model.set("custom")
        custom_frame.pack(pady=5)
        custom_model_entry.insert(0, current_model)
    
    # Add shortcut configuration
    shortcut_label = ctk.CTkLabel(dialog, text="Set Shortcut (e.g., ctrl+shift+'): ", wraplength=350)
    shortcut_label.pack(pady=10)
    
    shortcut_entry = ctk.CTkEntry(dialog, width=350)
    shortcut_entry.insert(0, current_config.get("shortcut", "ctrl+shift+'"))
    shortcut_entry.pack(pady=5)

    def save_model_and_shortcut():
        shortcut = shortcut_entry.get().strip()
        
        # Get the selected model
        model = selected_model.get()
        if model == "custom":
            custom_model = custom_model_entry.get().strip()
            if not custom_model:
                messagebox.showerror("Error", "Please enter a custom model name")
                return
            model = custom_model
        
        if model and shortcut:
            try:
                save_config(current_config.get("api_token", ""), model, shortcut)
                dialog.destroy()
                messagebox.showinfo("Success", "Preferences saved successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")
        else:
            messagebox.showerror("Error", "Please select a model and enter a valid shortcut")

    save_btn = ctk.CTkButton(dialog, text="Save Preferences", command=save_model_and_shortcut)
    save_btn.pack(pady=20)
    
    # Center dialog
    dialog.update_idletasks()
    width = dialog.winfo_width()
    height = dialog.winfo_height()
    x = (dialog.winfo_screenwidth() // 2) - (width // 2)
    y = (dialog.winfo_screenheight() // 2) - (height // 2)
    dialog.geometry(f"+{x}+{y}")

def show_token_dialog():
    """Show token entry dialog using customtkinter"""
    dialog = ctk.CTkToplevel()
    dialog.title("API Token Configuration")
    dialog.geometry("400x200")
    dialog.attributes('-topmost', True)
    
    label = ctk.CTkLabel(dialog, text="Enter your API token:", wraplength=350)
    label.pack(pady=10)
    
    token_entry = ctk.CTkEntry(dialog, width=350, show="•")
    token_entry.pack(pady=5)
    
    def save_token():
        token = token_entry.get().strip()
        if token:
            save_config(token)
            dialog.destroy()
            # show_toast("Token saved successfully!")
            messagebox.showinfo("Success", "Token saved successfully!")
        else:
            messagebox.showerror("Error", "Please enter a valid token")

    save_btn = ctk.CTkButton(dialog, text="Save Token", command=save_token)
    save_btn.pack(pady=10)
    
    # Center dialog
    dialog.update_idletasks()
    width = dialog.winfo_width()
    height = dialog.winfo_height()
    x = (dialog.winfo_screenwidth() // 2) - (width // 2)
    y = (dialog.winfo_screenheight() // 2) - (height // 2)
    dialog.geometry(f"+{x}+{y}")

def create_image():
    """Load and prepare custom 64x64 PNG as system tray icon"""
    try:
        # Load your image file (replace with your actual image path)
        image = Image.open("icon.png")  # <-- PUT YOUR ACTUAL PATH HERE
        
        # Convert to RGBA if not already (for transparency support)
        image = image.convert("RGBA")
        
        # Resize to exactly 64x64 pixels using Lanczos filter
        if image.size != (64, 64):
            image = image.resize((64, 64), Image.Resampling.LANCZOS)
            
        # Create circular mask if needed (optional)
        mask = Image.new('L', (64, 64), 0)
        draw = ImageDraw.Draw(mask) 
        draw.ellipse((0, 0, 64, 64), fill=255)
        
        # Apply mask if you want circular format (optional)
        image.putalpha(mask)
        
        return image
    except Exception as e:
        print(f"Error loading custom icon: {e}")
        # Fallback to default blue square
        fallback = Image.new('RGB', (64, 64), (255, 255, 255))
        draw = ImageDraw.Draw(fallback)
        draw.rectangle((16, 16, 48, 48), fill=(0, 0, 255))
        return fallback

def setup_tray_icon():
    global tray_icon
    image = create_image()
    menu = (
        item('Configure Token', lambda: root.after(0, show_token_dialog)),
        item('Configure Clippy', lambda: root.after(0, show_model_dialog)),
        item('Exit', lambda icon, item: exit_app()),
    )
    tray_icon = Icon("Clippy AI", image, "Clippy AI", menu)
    tray_icon.run()

def get_selected_text():
    original_clipboard = pyperclip.paste()
    keyboard.send('ctrl+c')
    time.sleep(0.1)
    selected_text = pyperclip.paste().strip()
    pyperclip.copy(original_clipboard)
    return selected_text

def show_popup(text):
    conversation_history = []  # Store conversation history
    
    def send_to_ai():
        config = load_config()
        if not config.get("api_token"):
            messagebox.showerror("Error", "API token not configured!")
            show_token_dialog()
            return

        user_questions = ask_box.get("0.0", "end").strip()
        
        # Disable the send button while processing
        send_button.configure(state="disabled")
        result_text.configure(state="normal")
        result_text.insert("end", "\n\nProcessing...")
        result_text.configure(state="disabled")
        
        def make_api_request():
            try:
                headers = {
                    "Authorization": f"Bearer {config['api_token']}",
                    "Content-Type": "application/json"
                }
                
                # Build messages including conversation history
                messages = [
                    {
                        "role": "system",
                        "content": "You are a helpful AI assistant."
                    },
                    {
                        "role": "user",
                        "content": f"Context: {text}"
                    }
                ]
                
                # Add conversation history
                messages.extend(conversation_history)
                
                # Add current question
                messages.append({
                    "role": "user",
                    "content": user_questions
                })
                
                payload = {
                    "model": config.get("model", DEFAULT_MODEL),
                    "messages": messages
                }
                
                resp = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                if resp.status_code == 401:
                    popup.after(0, lambda: messagebox.showerror("Error", "Invalid API token. Please reconfigure."))
                    popup.after(0, show_token_dialog)
                    return
                
                resp.raise_for_status()
                
                response_data = resp.json()
                if not response_data.get("choices"):
                    raise ValueError("No choices in response")
                    
                reply = response_data["choices"][0]["message"]["content"]
                
                # Update conversation history
                conversation_history.append({"role": "user", "content": user_questions})
                conversation_history.append({"role": "assistant", "content": reply})
                
                def update_result():
                    result_text.configure(state="normal")
                    
                    # Get all content and split into lines
                    content = result_text.get("1.0", "end-1c")
                    lines = content.split('\n')
                    
                    # Remove the "Processing..." line if it exists
                    if lines and lines[-1].strip() == "Processing...":
                        # Delete the last line containing "Processing..."
                        result_text.delete("end-2l", "end-1c")
                    
                    # Add the new message
                    result_text.insert("end", f"\n\nYou: {user_questions}\nAI: {reply}")
                    result_text.see("end")  # Scroll to the bottom
                    result_text.configure(state="disabled")
                    ask_box.delete("0.0", "end")  # Clear the question box
                
                popup.after(0, update_result)
                
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                popup.after(0, lambda: update_error_text(error_msg))
            finally:
                popup.after(0, lambda: send_button.configure(state="normal"))
        
        def update_error_text(error_msg):
            result_text.configure(state="normal")
            result_text.insert("end", f"\n\nError: {error_msg}")
            result_text.configure(state="disabled")
        
        # Run API request in a separate thread to prevent GUI freezing
        threading.Thread(target=make_api_request, daemon=True).start()

    # Create popup window and UI elements
    popup = ctk.CTkToplevel(root)
    popup.title("Clippy AI")
    popup.geometry("600x800")  # Made larger to accommodate conversation history
    popup.attributes('-topmost', True)
    popup.focus_force()

    # Center the popup on screen
    screen_width = popup.winfo_screenwidth()
    screen_height = popup.winfo_screenheight()
    x = (screen_width - 600) // 2
    y = (screen_height - 800) // 2
    popup.geometry(f"600x800+{x}+{y}")

    # Selected Text Label
    selected_text_label = ctk.CTkLabel(popup, text="Selected Text:", font=("Segoe UI", 12, "bold"))
    selected_text_label.pack(pady=(15, 5), padx=15, anchor="w")

    # Read-only textbox for selected text
    selected_text_box = ctk.CTkTextbox(popup, width=550, height=100)
    selected_text_box.insert("0.0", text)
    selected_text_box.configure(state="disabled")
    selected_text_box.pack(pady=(0, 15), padx=15)

    # Conversation History Label
    history_label = ctk.CTkLabel(popup, text="Conversation:", font=("Segoe UI", 12, "bold"))
    history_label.pack(pady=(0, 5), padx=15, anchor="w")

    # Scrollable conversation history
    result_text = ctk.CTkTextbox(popup, width=550, height=400, wrap="word")
    result_text.pack(pady=(0, 15), padx=15, fill="both", expand=True)
    result_text.configure(state="disabled")

    # User Questions Label
    questions_label = ctk.CTkLabel(popup, text="Your Question:", font=("Segoe UI", 12, "bold"))
    questions_label.pack(pady=(0, 5), padx=15, anchor="w")

    # Editable textbox for user questions
    ask_box = ctk.CTkTextbox(popup, width=550, height=100)
    ask_box.pack(pady=(0, 15), padx=15)

    # Send to AI Button
    send_button = ctk.CTkButton(popup, text="Send to AI", command=send_to_ai)
    send_button.pack(pady=(0, 15), padx=15)

def on_hotkey():
    config = load_config()
    if not config.get("api_token"):
        root.after(0, show_token_dialog)
        return
    
    selected_text = get_selected_text()
    if selected_text:
        root.after(0, show_popup, selected_text)

def exit_app():
    """Handle application exit"""
    global tray_icon
    if tray_icon is not None:
        tray_icon.stop()
    root.quit()
    root.destroy()

if __name__ == "__main__":
    root = ctk.CTk()
    root.withdraw()  # Hide the main window

    # Load the current configuration to get the shortcut
    config = load_config()
    shortcut = config.get("shortcut", "ctrl+shift+'")

    # Start system tray icon in a daemon thread
    tray_thread = threading.Thread(target=setup_tray_icon, daemon=True)
    tray_thread.start()

    # Add hotkey for the user-defined shortcut
    keyboard.add_hotkey(shortcut, on_hotkey, suppress=True)
    keyboard.add_hotkey("ctrl+shift+q", exit_app)

    root.mainloop()

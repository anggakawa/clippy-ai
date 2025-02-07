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
from PIL import ImageGrab
import io
import base64
import tempfile
from datetime import datetime


# Add this near the top of your file, after the imports
AVAILABLE_MODELS = [
    "deepseek/deepseek-chat",
    "anthropic/claude-3.5-sonnet",
    "openai/chatgpt-4o-latest",
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
    toast_width = 300
    toast_height = 100
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

def create_default_icon():
    """Create a default icon with a simple whale design"""
    size = (64, 64)
    # Create transparent background
    image = Image.new('RGBA', size, color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Colors
    whale_color = '#2196F3'  # Blue color for the whale
    eye_color = 'white'
    
    # Main whale body (rounded rectangle)
    body_points = [
        (15, 20),  # Top left
        (50, 20),  # Top right
        (50, 44),  # Bottom right
        (15, 44)   # Bottom left
    ]
    draw.polygon(body_points, fill=whale_color)
    
    # Whale tail
    tail_points = [
        (50, 25),   # Base of tail
        (58, 15),   # Top tip
        (58, 35),   # Bottom tip
        (50, 39)    # Bottom of tail base
    ]
    draw.polygon(tail_points, fill=whale_color)
    
    # Whale spout
    spout_points = [
        (20, 20),   # Base
        (15, 10),   # Left tip
        (25, 10)    # Right tip
    ]
    draw.polygon(spout_points, fill=whale_color)
    
    # Eye
    draw.ellipse([22, 28, 26, 32], fill=eye_color)
    
    return image

def setup_tray_icon():
    global tray_icon
    image = create_default_icon()
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

# TODO: implement image grabbing
def get_selected_content():
    """Get either selected text or image from clipboard"""
    # First try to get image from clipboard
    try:
        image = ImageGrab.grabclipboard()
        if image:
            # Save image to temporary file
            temp_dir = tempfile.gettempdir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_path = f"{temp_dir}/clippy_image_{timestamp}.png"
            image.save(temp_path, 'PNG')
            
            # Convert image to base64 for API
            with open(temp_path, 'rb') as img_file:
                base64_image = base64.b64encode(img_file.read()).decode('utf-8')
            
            # Clean up temp file
            os.remove(temp_path)
            
            return {
                'type': 'image',
                'content': base64_image,
                'display': image
            }
    except Exception as e:
        print(f"Error handling image: {e}")

    # If no image, try to get text
    original_clipboard = pyperclip.paste()
    keyboard.send('ctrl+c')
    time.sleep(0.1)
    selected_text = pyperclip.paste().strip()
    pyperclip.copy(original_clipboard)
    
    if selected_text:
        return {
            'type': 'text',
            'content': selected_text,
            'display': selected_text
        }
    
    return None

def show_popup(text):
    conversation_history = []  # Store conversation history
    
    def send_to_ai():
        config = load_config()
        if not config.get("api_token"):
            messagebox.showerror("Error", "API token not configured!")
            show_token_dialog()
            return

        user_questions = ask_box.get("0.0", "end").strip()
        
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
                    }
                ]
                
                # Add context only if there's no conversation history
                if not conversation_history:
                    messages.append({
                        "role": "user",
                        "content": f"Context: {text}"
                    })
                
                # Add conversation history
                messages.extend(conversation_history)
                
                # Add current question
                messages.append({
                    "role": "user",
                    "content": user_questions
                })
                
                payload = {
                    "model": config.get("model", DEFAULT_MODEL),
                    "messages": messages,
                    "stream": True  # Enable streaming
                }
                
                # Make streaming request
                with requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30,
                    stream=True
                ) as resp:
                    
                    if resp.status_code == 401:
                        popup.after(0, lambda: messagebox.showerror("Error", "Invalid API token. Please reconfigure."))
                        popup.after(0, show_token_dialog)
                        return
                    
                    resp.raise_for_status()
                    accumulated_message = ""

                    def update_text_widget(new_text):
                        result_text.configure(state="normal")
                        result_text.insert("end", new_text)
                        result_text.see("end")
                        result_text.configure(state="disabled")

                    # Insert the user's question first
                    popup.after(0, lambda: update_text_widget(f"\n\nYou: {user_questions}\nAI: "))

                    for line in resp.iter_lines():
                        if line:
                            try:
                                line = line.decode('utf-8')
                                if line.startswith('data: '):
                                    line = line[6:]  # Remove 'data: ' prefix
                                    if line.strip() == '[DONE]':
                                        break
                                    
                                    json_data = json.loads(line)
                                    if 'choices' in json_data:
                                        delta = json_data['choices'][0].get('delta', {})
                                        if 'content' in delta:
                                            content = delta['content']
                                            accumulated_message += content
                                            popup.after(0, lambda c=content: update_text_widget(c))
                            except json.JSONDecodeError:
                                continue
                            except Exception as e:
                                print(f"Error processing stream: {e}")
                                break

                    # Update conversation history after streaming is complete
                    conversation_history.append({"role": "user", "content": user_questions})
                    conversation_history.append({"role": "assistant", "content": accumulated_message})
                    
                    # Clear the question box
                    popup.after(0, lambda: ask_box.delete("0.0", "end"))
                
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

    popup = ctk.CTkToplevel(root)
    popup.title("Clippy AI")
    popup.geometry("600x500")
    popup.attributes('-topmost', True)
    popup.focus_force()

    # Center the popup on screen
    screen_width = popup.winfo_screenwidth()
    screen_height = popup.winfo_screenheight()
    x = (screen_width - 600) // 2
    y = (screen_height - 500) // 2
    popup.geometry(f"600x500+{x}+{y}")

    # Configure grid so widgets align and expand properly
    popup.grid_columnconfigure(0, weight=1)
    popup.grid_columnconfigure(1, weight=0)

    # Selected Text Label
    selected_label = ctk.CTkLabel(popup, text="Selected Text:", font=("Segoe UI", 12, "bold"))
    selected_label.grid(row=0, column=0, columnspan=2, padx=15, pady=(15, 5), sticky="w")

    # Read-only textbox for selected text
    selected_box = ctk.CTkTextbox(popup, width=570, height=80)
    selected_box.insert("0.0", text)
    selected_box.configure(state="disabled")
    selected_box.grid(row=1, column=0, columnspan=2, padx=15, pady=(0, 15), sticky="ew")

    # User Questions Label
    questions_label = ctk.CTkLabel(popup, text="Your Question:", font=("Segoe UI", 12, "bold"))
    questions_label.grid(row=2, column=0, columnspan=2, padx=15, pady=(0, 5), sticky="w")

    # Editable textbox for user questions
    ask_box = ctk.CTkTextbox(popup, width=400, height=50)
    ask_box.grid(row=3, column=0, padx=(15, 5), pady=(0, 15), sticky="ew")

    # Send to AI Button
    send_button = ctk.CTkButton(popup, text="Send to AI", command=send_to_ai)
    send_button.grid(row=3, column=1, padx=(5, 15), pady=(0, 15), sticky="nsew")

    # Conversation History Label
    history_label = ctk.CTkLabel(popup, text="Conversation:", font=("Segoe UI", 12, "bold"))
    history_label.grid(row=4, column=0, columnspan=2, padx=15, pady=(0, 5), sticky="w")

    # Scrollable conversation history textbox
    result_text = ctk.CTkTextbox(popup, width=570, height=200, wrap="word")
    result_text.configure(state="disabled")
    result_text.grid(row=5, column=0, columnspan=2, padx=15, pady=(0, 15), sticky="nsew")

    # Let the conversation history textbox expand with the window
    popup.grid_rowconfigure(5, weight=1)

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

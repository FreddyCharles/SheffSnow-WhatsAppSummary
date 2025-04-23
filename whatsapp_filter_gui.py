import re
from datetime import datetime, timedelta
import os
import tkinter as tk
from tkinter import ttk  # For themed widgets (optional, makes it look slightly better)
from tkinter import filedialog, messagebox
import zipfile
import shutil # For potentially removing the extraction folder later if desired

# --- Constants ---
EXTRACTION_SUBFOLDER = "extracted_chat" # Name of the subfolder for extracted files

# --- Core Filtering Logic (is_automated_message, parse_whatsapp_date, filter_whatsapp_chat) ---
# --- These functions remain unchanged. Paste them here. ---

def parse_whatsapp_date(date_str):
    """Parses a DD/MM/YYYY string to a date object."""
    try:
        # Handle potential variations if needed, e.g., YYYY/MM/DD
        return datetime.strptime(date_str, "%d/%m/%Y").date()
    except ValueError:
        # Add more formats if exports differ significantly
        # Example: return datetime.strptime(date_str, "%Y/%m/%d").date()
        raise # Re-raise if no known format matches

def is_automated_message(sender_name, message_content):
    """Checks if a message is an automated system message."""
    lower_content = message_content.lower().strip()
    normalized_sender = sender_name.replace('\u200e', '').strip()

    exact_phrases = [
        "this group was created", "you created this community", "you created this group",
        "missed voice call", "missed video call", "started a call",
        "this message was deleted", "[message deleted]",
        "messages and calls are end-to-end encrypted. no one outside of this chat, not even whatsapp, can read or listen to them. click to learn more.",
        "messages and calls are end-to-end encrypted.",
        "you joined using this group's invite link",
        "you joined using this community's invite link",
        # Add other common system messages or placeholders if needed
        "created the poll:", # Example poll detection
    ]
    if lower_content in exact_phrases: return True
    # Handle cases like "[Image Omitted]" if you want to filter those too
    if lower_content.startswith("[") and lower_content.endswith(" omitted]"): return True

    if sender_name == "Me/System":
        action_keywords_start = [
            "you added", "you removed", "you left", "you joined", "you created", "you changed",
            "you're now an admin", "you are now an admin",
            "you're no longer an admin", "you are no longer an admin"
        ]
        if any(lower_content.startswith(phrase) for phrase in action_keywords_start): return True
        if "changed the subject to" in lower_content: return True
        if "changed this group's icon" in lower_content: return True
        if "security code changed." in lower_content: return True
        if "added you" in lower_content: return True
        if "created the announcement group" in lower_content: return True
        if "updated the community info" in lower_content: return True

    else: # Sender is specific user
        if lower_content.startswith(normalized_sender.lower()):
            action_part = lower_content[len(normalized_sender):].strip()
            action_verbs = [
                "added", "removed", "left", "joined", "created group",
                "changed the subject", "changed this group's icon",
                "was added", "was removed", "changed their phone number"
            ]
            if any(action_part.startswith(verb) for verb in action_verbs): return True
        if ("was added" in lower_content or "was removed" in lower_content) and (" by " in lower_content): return True

    if "changed their phone number to a new number." in lower_content: return True
    if "changed to a new number. tap to message or add the new number." in lower_content: return True
    if f"{normalized_sender.lower()} changed their phone number" in lower_content: return True
    if "your security code with" in lower_content and "changed" in lower_content: return True

    return False


def filter_whatsapp_chat(input_filepath, output_filepath):
    """
    Reads a WhatsApp chat file, filters messages, and writes to an output file.
    Returns True on success, False on failure. Raises exceptions for specific file errors.
    """
    today = datetime.now().date()
    seven_days_ago = today - timedelta(days=7)
    message_start_regex = re.compile(
        r"^\[(\d{2}/\d{2}/\d{4}),\s*(\d{1,2}:\d{2}:\d{2}(?:\s*[AP]M)?)\s*\]\s*(?:\u200e)?\s*([^:]+?):\s*(.*)"
    )

    kept_message_blocks = []
    current_message_block = []
    current_message_is_valid = False
    lines_processed = 0
    messages_kept = 0
    malformed_lines = 0
    line_number = 0 # Initialize line number

    try:
        with open(input_filepath, 'r', encoding='utf-8') as infile:
            for line_number, line in enumerate(infile, 1):
                lines_processed += 1
                match = message_start_regex.match(line)

                if match:
                    if current_message_block and current_message_is_valid:
                        kept_message_blocks.append("".join(current_message_block))
                        messages_kept += 1
                    current_message_block = []
                    current_message_is_valid = False
                    date_str, _, sender_name, message_first_line = match.groups()
                    sender_name = sender_name.strip()

                    try:
                        msg_date = parse_whatsapp_date(date_str)
                        if msg_date >= seven_days_ago:
                            if not is_automated_message(sender_name, message_first_line.strip()):
                                current_message_is_valid = True
                                current_message_block.append(line)
                    except ValueError:
                        malformed_lines += 1
                else:
                    if current_message_block and current_message_is_valid:
                        current_message_block.append(line)
                    # Consider logging or counting lines that are non-empty but don't match
                    # elif line.strip(): malformed_lines += 1

            if current_message_block and current_message_is_valid:
                kept_message_blocks.append("".join(current_message_block))
                messages_kept += 1

    except FileNotFoundError:
        raise FileNotFoundError(f"Input file not found: {input_filepath}")
    except Exception as e:
        raise RuntimeError(f"Error processing input file near line {line_number}: {e}")

    if malformed_lines > 0:
        print(f"Warning: Encountered {malformed_lines} lines with unexpected formats or invalid dates.")

    try:
        with open(output_filepath, 'w', encoding='utf-8') as outfile:
            outfile.write(f"# Filtered WhatsApp Chat - Messages from {seven_days_ago.strftime('%d/%m/%Y')} onwards, excluding automated.\n")
            outfile.write(f"# Original file processed: {os.path.basename(input_filepath)}\n")
            outfile.write(f"# Filtered on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            if not kept_message_blocks:
                outfile.write("# No messages matched the filtering criteria.\n")
            else:
                outfile.write("".join(kept_message_blocks)) # Join blocks directly

    except IOError as e:
        raise IOError(f"Could not write to output file: {output_filepath}\nError: {e}")
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred during writing: {e}")

    return True, lines_processed, messages_kept


# --- GUI Application Class ---

class ChatFilterApp:
    def __init__(self, master):
        self.master = master
        master.title("WhatsApp Chat Filter Tool")
        # master.geometry("500x350") # Optional: set initial size

        # --- Style ---
        self.style = ttk.Style()
        self.style.theme_use('clam') # 'clam', 'alt', 'default', 'classic'

        # --- Variables ---
        self.zip_filepath = tk.StringVar()
        self.txt_filepath = tk.StringVar()
        self.extraction_path = tk.StringVar()
        self.extract_status = tk.StringVar()

        # --- Layout ---
        # Frame for Step 1: ZIP Extraction
        self.frame_zip = ttk.LabelFrame(master, text="Step 1: Select & Extract ZIP", padding=(10, 5))
        self.frame_zip.pack(pady=10, padx=10, fill="x")

        ttk.Button(self.frame_zip, text="Select ZIP File", command=self.select_zip).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ttk.Label(self.frame_zip, textvariable=self.zip_filepath, relief="sunken", width=40).grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.btn_extract = ttk.Button(self.frame_zip, text="Extract ZIP Contents", command=self.extract_zip_contents, state="disabled")
        self.btn_extract.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        ttk.Label(self.frame_zip, textvariable=self.extract_status).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        # Frame for Step 2: File Selection & Filtering
        self.frame_filter = ttk.LabelFrame(master, text="Step 2: Select TXT File & Filter", padding=(10, 5))
        self.frame_filter.pack(pady=10, padx=10, fill="x")

        self.btn_select_txt = ttk.Button(self.frame_filter, text="Select TXT File", command=self.select_txt_file, state="disabled")
        self.btn_select_txt.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ttk.Label(self.frame_filter, textvariable=self.txt_filepath, relief="sunken", width=40).grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.btn_filter = ttk.Button(self.frame_filter, text="Filter Selected File", command=self.run_filter_on_selected, state="disabled")
        self.btn_filter.grid(row=1, column=0, columnspan=2, padx=5, pady=10, sticky="ew")

        # Configure column weights for resizing
        self.frame_zip.columnconfigure(1, weight=1)
        self.frame_filter.columnconfigure(1, weight=1)

    def select_zip(self):
        """Opens file dialog to select ZIP file."""
        filepath = filedialog.askopenfilename(
            title="Select WhatsApp Chat Export ZIP File",
            filetypes=[("Zip archives", "*.zip"), ("All files", "*.*")]
        )
        if filepath:
            self.zip_filepath.set(filepath)
            self.btn_extract.config(state="normal") # Enable extract button
            # Reset downstream steps if a new ZIP is selected
            self.txt_filepath.set("")
            self.extract_status.set("")
            self.extraction_path.set("")
            self.btn_select_txt.config(state="disabled")
            self.btn_filter.config(state="disabled")

    def extract_zip_contents(self):
        """Extracts the contents of the selected ZIP file."""
        zip_path = self.zip_filepath.get()
        if not zip_path:
            messagebox.showerror("Error", "No ZIP file selected.")
            return

        # Define extraction path (subfolder in the same directory as the script)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        extract_to = os.path.join(script_dir, EXTRACTION_SUBFOLDER)
        self.extraction_path.set(extract_to) # Store for later use

        self.extract_status.set("Extracting...")
        self.master.update_idletasks() # Update GUI immediately

        try:
            # Create extraction folder if it doesn't exist
            os.makedirs(extract_to, exist_ok=True)

            # Clear the folder first? Optional, depends on desired behavior
            # Be careful with shutil.rmtree!
            # print(f"Clearing previous contents of {extract_to}...")
            # for item in os.listdir(extract_to):
            #     item_path = os.path.join(extract_to, item)
            #     try:
            #         if os.path.isfile(item_path) or os.path.islink(item_path):
            #             os.unlink(item_path)
            #         elif os.path.isdir(item_path):
            #             shutil.rmtree(item_path)
            #     except Exception as e:
            #         print(f"Warning: Failed to remove {item_path}: {e}")


            with zipfile.ZipFile(zip_path, 'r') as zf:
                # Check for the TXT file *before* extracting everything (optional)
                txt_files = [n for n in zf.namelist() if n.lower().endswith(".txt") and not n.startswith('__MACOSX')]
                if not txt_files:
                    raise ValueError("No '.txt' file found in the ZIP archive.")
                if len(txt_files) > 1:
                     # If multiple TXT files, extract all but warn user they need to select correct one
                     print(f"Warning: Multiple .txt files found in ZIP: {', '.join(txt_files)}")
                     # raise ValueError(f"Multiple '.txt' files found: {', '.join(txt_files)}. Extraction aborted.")

                print(f"Extracting all contents to: {extract_to}")
                zf.extractall(path=extract_to)

            self.extract_status.set(f"Extracted to '{EXTRACTION_SUBFOLDER}' folder.")
            self.btn_select_txt.config(state="normal") # Enable next step
            self.btn_extract.config(state="disabled") # Disable extraction button

        except zipfile.BadZipFile:
            self.extract_status.set("Error: Invalid ZIP file.")
            messagebox.showerror("Error", f"Not a valid ZIP file:\n{os.path.basename(zip_path)}")
            self.btn_extract.config(state="normal") # Re-enable if failed
        except ValueError as ve: # Catch specific error like no TXT file
            self.extract_status.set(f"Error: {ve}")
            messagebox.showerror("Extraction Error", str(ve))
            self.btn_extract.config(state="normal")
        except Exception as e:
            self.extract_status.set("Error during extraction.")
            messagebox.showerror("Extraction Error", f"An error occurred:\n{e}")
            self.btn_extract.config(state="normal") # Re-enable if failed

    def select_txt_file(self):
        """Opens file dialog to select the extracted TXT file."""
        initial_dir = self.extraction_path.get() # Start in the extraction folder
        if not initial_dir or not os.path.isdir(initial_dir):
             initial_dir = os.path.dirname(self.zip_filepath.get()) # Fallback

        filepath = filedialog.askopenfilename(
            title="Select the Extracted WhatsApp Chat TXT File",
            initialdir=initial_dir, # Start browsing here
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filepath:
            # Basic check if selected file is inside the expected extraction folder
            if self.extraction_path.get() and not filepath.startswith(self.extraction_path.get()):
                 messagebox.showwarning("Warning", "The selected file is outside the extraction folder. Please ensure it's the correct extracted chat file.")
            self.txt_filepath.set(filepath)
            self.btn_filter.config(state="normal") # Enable filter button

    def run_filter_on_selected(self):
        """Runs the filtering logic on the selected TXT file."""
        input_txt = self.txt_filepath.get()
        if not input_txt:
            messagebox.showerror("Error", "No TXT file selected for filtering.")
            return

        # --- Generate Output Filename ---
        try:
            # Save output near the original ZIP file or the script location as fallback
            output_dir = os.path.dirname(self.zip_filepath.get()) if self.zip_filepath.get() else os.path.dirname(os.path.abspath(__file__))
            base_name = os.path.basename(input_txt)
            name_part, _ = os.path.splitext(base_name)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"{name_part}_filtered_{timestamp}.txt"
            output_filepath = os.path.join(output_dir, output_filename)
        except Exception as e:
            messagebox.showerror("Error", f"Could not determine output file path: {e}")
            return

        # --- Run the Filtering ---
        try:
            print(f"Input for filtering: {input_txt}")
            print(f"Output file: {output_filepath}")
            self.master.config(cursor="watch") # Indicate processing
            self.master.update_idletasks()

            success, lines_processed, messages_kept = filter_whatsapp_chat(input_txt, output_filepath)

            self.master.config(cursor="") # Reset cursor

            if success:
                if messages_kept > 0:
                    messagebox.showinfo("Success",
                                        f"Chat filtered successfully!\n\n"
                                        f"Processed {lines_processed} lines from '{os.path.basename(input_txt)}'.\n"
                                        f"Kept {messages_kept} messages.\n\n"
                                        f"Saved to:\n{output_filepath}")
                else:
                    messagebox.showwarning("Completed",
                                          f"Processing complete, but no messages matched the criteria.\n\n"
                                          f"Processed {lines_processed} lines from '{os.path.basename(input_txt)}'.\n"
                                          f"Filtered output saved to:\n{output_filepath}")
            # filter_whatsapp_chat raises exceptions on failure now

        except (FileNotFoundError, IOError, RuntimeError) as e:
            self.master.config(cursor="")
            print(f"Error during filtering: {e}")
            messagebox.showerror("Filtering Error", f"An error occurred during filtering:\n\n{e}")
        except Exception as e:
            self.master.config(cursor="")
            print(f"Unexpected Error during filtering: {e}")
            messagebox.showerror("Unexpected Error", f"An unexpected error occurred during filtering:\n\n{e}")
        finally:
            # Consider re-enabling buttons or adding a reset button
            # self.btn_filter.config(state="disabled")
            # self.btn_select_txt.config(state="normal")
             pass


# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = ChatFilterApp(root)
    root.mainloop()
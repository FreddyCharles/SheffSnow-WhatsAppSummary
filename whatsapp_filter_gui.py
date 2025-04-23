# --- START OF FULL SCRIPT ---
import re
from datetime import datetime, timedelta
import os
import tkinter as tk
from tkinter import ttk # For themed widgets like Combobox
from tkinter import filedialog, messagebox
import zipfile
import shutil

# --- Constants ---
EXTRACTION_SUBFOLDER = "extracted_chat" # Name of the subfolder for extracted files
PROMPT_TEMPLATE = """Analyze the following text, which is a .txt export from our snowsports club's WhatsApp announcement chat (specifically, the filtered content found in the file '{filtered_filename}'). Your task is to:

Identify the timeframe: Determine the date range covering the most recent {time_frame_days} days based on the timestamps/dates within this chat log.

Filter by Time: Focus exclusively on messages sent within that most recent {time_frame_days}-day period. Pay close attention to the dates associated with each message.

Filter by Content Relevance: Extract only the substantive announcements and key information shared during that {time_frame_days}-day period. This includes:

Details of upcoming events (what, when, where, cost, sign-up info).

Information about trips (destination, dates, deadlines, links).

All mentioned deadlines (payments, forms, applications).

Important club updates (committee news, kit info, policy changes).

Calls to action (voting, surveys, requests for volunteers).

Important links shared.

Exclude Irrelevant Content: Strictly ignore messages older than the identified {time_frame_days}-day period. Also, ignore conversational filler, simple replies ("Ok", "Thanks", emojis), basic questions that don't contain new info, off-topic chat, and standard system messages (like "[user] joined/left" or message timestamps/sender names if they aren't part of the core announcement message itself).

Summarize: Provide a fun tl;dr (too long; didn't read) style summary of the relevant information extracted from the specified {time_frame_days}-day timeframe. Start with a short, engaging introductory sentence or two. Then, structure the main points clearly using bullet points, potentially grouped by topic (e.g., Events, Deadlines, Updates) for easy reading. Keep the tone light and informal while ensuring all key info is captured."""

# --- Core Filtering Logic ---

def parse_whatsapp_date(date_str):
    """
    Parses a date string using multiple common formats, prioritizing DD/MM/YYYY.
    Returns a date object or raises ValueError if no format matches.
    """
    formats_to_try = [
        "%d/%m/%Y",  # Example format: 22/04/2025
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%d.%m.%Y",
        "%d-%m-%Y",
        "%d/%m/%y",  # Short year versions
        "%m/%d/%y"
    ]

    for fmt in formats_to_try:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue # Try the next format
    raise ValueError(f"Date '{date_str}' did not match any known formats: {formats_to_try}")


# --- START OF REVISED is_automated_message FUNCTION ---
def is_automated_message(sender_name, message_content):
    """
    Checks if a message is likely an automated system message based on content
    patterns or specific sender formats associated with system actions.
    More rigorous checks for various system message types.
    Returns True if automated, False otherwise.
    """
    # Normalize content: lowercase, strip ends, remove LRM, normalize internal whitespace
    lower_content = ' '.join(message_content.lower().strip().replace('\u200e', '').split())
    # Normalize sender: strip ends, remove LRM
    normalized_sender = sender_name.strip().replace('\u200e', '')

    # --- 1. Exact System Phrases & Omissions ---
    exact_phrases = [
        "this message was deleted",
        "this reply was deleted.",
        "missed voice call", # Often followed by duration/time
        "missed video call", # Often followed by duration/time
        "messages and calls are end-to-end encrypted. no one outside of this chat, not even whatsapp, can read or listen to them.",
        "messages and calls are end-to-end encrypted.",
        "‎image omitted",
        "‎video omitted",
        "‎audio omitted",
        "‎sticker omitted",
        "‎gif omitted",
        "‎document omitted",
        "‎contact card omitted", # Added variation
        "‎contact omitted",
        "‎location omitted",
        "poll:", # Often followed by poll details
        # Add other language variations if needed
    ]
    if lower_content in exact_phrases or \
       (lower_content.startswith("[") and lower_content.endswith(" omitted]")): # Handles "[ média omitido ]" etc.
        # print(f"  DEBUG (is_automated): Filtered by exact phrase/omitted: '{lower_content[:50]}...'")
        return True

    # --- 2. Group Setting/Info Change Messages ---
    # These usually have a normal sender but describe an action
    group_change_phrases_contain = [
        "changed the subject from", # e.g., "[Admin] changed the subject from 'Old' to 'New'"
        "changed the group description", # e.g., "[Admin] changed the group description"
        "changed this group's icon",
        "changed their phone number to a new number.", # e.g., "[User] changed their phone number..."
        "changed to a new number. tap to message or add the new number.", # Also user specific
        "your security code with", # followed by 'changed.' usually
        "created group", # e.g., "[User] created group '[Name]'"
        "created community", # e.g., "[User] created community '[Name]'"
        "you're now an admin", "you are now an admin",
        "you're no longer an admin", "you are no longer an admin",
        "pinned a message", # e.g., "[User] pinned a message" / "You pinned a message"
        "unpinned a message", # e.g., "[User] unpinned a message" / "You unpinned a message"
        "turned on disappearing messages",
        "turned off disappearing messages",
        "changed the message timer",
        "now allows messages to be kept in the chat", # Disappearing messages update
        "linked this group to community", # e.g., "[Admin] linked this group to community '[Name]'"
        "unlinked this group from its community",
        "moved this group to community",
        "started a call", # Includes group calls
        "call ended", # Added
        "ended the call", # Added variation
        "created the poll:", # Content starts with this
    ]
    if any(phrase in lower_content for phrase in group_change_phrases_contain):
        # Specific check for security code change
        if "your security code with" in lower_content and "changed." in lower_content:
             # print(f"  DEBUG (is_automated): Filtered by security code change: '{lower_content[:50]}...'")
             return True
        # Filter if other phrases are present (and it's not the security code one)
        if not ("your security code with" in lower_content):
             # print(f"  DEBUG (is_automated): Filtered by group change phrase: '{lower_content[:50]}...'")
             return True

    # --- 3. Join/Leave/Add/Remove Messages ---
    # These patterns often appear without a specific sender name before the colon,
    # or the "sender" part might be the person who was affected.
    # Sometimes the whole action is the message content (handled by V2 regex in main loop).

    # Specific Sender Format: "~ Name: left"
    if normalized_sender.startswith("~ ") and lower_content == "left":
        # print(f"  DEBUG (is_automated): Filtered by sender '~ ' and exact content 'left'")
        return True

    # Content-based checks (often matches V2 format where message_content is the full action line)

    # Joining
    if "joined using this group's invite link" in lower_content or \
       "joined using this community's invite link" in lower_content or \
       "joined" == lower_content: # Simple "[Number/Name] joined"
        # print(f"  DEBUG (is_automated): Filtered by join pattern: '{lower_content[:50]}...'")
        return True

    # Adding / Removing (more specific checks)
    # Matches "[Admin/You] added [User/Number]" or "[User/Number] was added [by Admin]"
    if lower_content.startswith("you added ") or \
       lower_content.endswith(" was added") or \
       " was added by " in lower_content:
        # print(f"  DEBUG (is_automated): Filtered by add pattern: '{lower_content[:50]}...'")
        return True

    # Matches "[Admin/You] removed [User/Number]" or "[User/Number] was removed [by Admin]"
    if lower_content.startswith("you removed ") or \
       lower_content.endswith(" was removed") or \
       " was removed by " in lower_content:
        # print(f"  DEBUG (is_automated): Filtered by remove pattern: '{lower_content[:50]}...'")
        return True

    # Leaving (handles "[Number/Name] left" which often matches V2 format)
    if lower_content.endswith(" left"):
        # To avoid filtering "we left the party", check if it's *just* "[name/number] left"
        parts = lower_content.split()
        if len(parts) <= 3 and parts[-1] == "left": # Allows for names with spaces e.g., "John Doe left"
            # print(f"  DEBUG (is_automated): Filtered by left pattern: '{lower_content[:50]}...'")
            return True


    # --- 4. Phone Number Check (Optional future refinement) ---
    # if re.fullmatch(r"\+?\d[\d\s()-]+", normalized_sender): # Matches common phone number patterns
    #     if lower_content in ["ok", "okay", "yes", "no", "👍", "✅"] or len(lower_content) < 10:
    #         pass # Don't filter based *only* on sender being a number + short message

    # If none of the above specific automated patterns matched, assume it's a user message.
    return False
# --- END OF REVISED is_automated_message FUNCTION ---


# --- FILTERING FUNCTION WITH DEBUGGING ---
def filter_whatsapp_chat(input_filepath, output_filepath, days_to_filter):
    """
    Reads WhatsApp chat file, filters messages by date and removes automated
    messages (including join/leave), then writes the result to an output file
    including the AI prompt at the top. Includes DEBUG prints.
    """
    today = datetime.now().date()
    filter_start_date = today - timedelta(days=days_to_filter) if days_to_filter != 99999 else datetime.min.date() # Handle 'All Time'
    filter_end_date_str = "Eternity" if days_to_filter == 99999 else today.strftime('%d/%m/%Y')
    print(f"DEBUG: Filtering messages from {filter_start_date.strftime('%d/%m/%Y')} up to {filter_end_date_str} ({days_to_filter} days history).")

    # Regex V1: Standard Message [Date, Time] Sender: Message
    message_start_regex = re.compile(
        r"^\["
        r"(\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4})"         # Date group (flexible format) - Group 1
        r",\s*"
        r"(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)"    # Time group (HH:MM or HH:MM:SS, opt AM/PM) - Group 2
        r"\s*\]"
        r"\s*(?:\u200e)?\s*"                         # Optional LRM/space
        r"([^:]+?)"                                  # Sender group (non-greedy until colon) - Group 3
        r":\s*"
        r"(.*)"                                      # Message group (rest of the line) - Group 4
        , re.IGNORECASE
    )

    # Regex V2: System Message like [Date, Time] Action Message (no colon sender)
    system_message_no_colon_regex = re.compile(
        r"^\["
        r"(\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4})"         # Date group - Group 1
        r",\s*"
        r"(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)"    # Time group - Group 2
        r"\s*\]"
        r"\s*(?:\u200e)?\s*"                         # Optional LRM/space
        r"(.*)"                                      # Action Message group (rest of the line) - Group 3
        , re.IGNORECASE
    )

    kept_message_blocks = []
    current_message_block = []
    current_message_is_valid = False
    lines_processed = 0
    messages_kept_count = 0
    automated_filtered_count = 0
    date_filtered_count = 0
    malformed_lines = 0
    line_number = 0

    try:
        print(f"DEBUG: Opening input file: {input_filepath}")
        with open(input_filepath, 'r', encoding='utf-8') as infile:
            for line_number, line in enumerate(infile, 1):
                lines_processed += 1
                line_strip = line.strip()
                if not line_strip: continue

                match = message_start_regex.match(line)
                match_system = None
                sender_name = ""
                message_text_for_check = ""
                is_system_format = False # Flag for V2 format

                if match: # Matched V1: [Date, Time] Sender: Message
                    if current_message_block and current_message_is_valid:
                        kept_message_blocks.append("".join(current_message_block))
                        messages_kept_count += 1
                    current_message_block = [line]
                    current_message_is_valid = False
                    date_str, time_str, sender_name_raw, message_first_line = match.groups()
                    sender_name = sender_name_raw.strip()
                    message_text_for_check = message_first_line.strip()

                else:
                    match_system = system_message_no_colon_regex.match(line)
                    if match_system: # Matched V2: [Date, Time] Action Text
                        if current_message_block and current_message_is_valid:
                            kept_message_blocks.append("".join(current_message_block))
                            messages_kept_count += 1
                        current_message_block = [line]
                        current_message_is_valid = False
                        is_system_format = True
                        date_str, time_str, action_text = match_system.groups()
                        sender_name = "" # No formal sender
                        message_text_for_check = action_text.strip()

                    else: # Continuation line or malformed
                        if current_message_block:
                            if current_message_is_valid:
                                current_message_block.append(line)
                        elif line_strip:
                            malformed_lines += 1
                            if malformed_lines <= 15:
                                print(f"WARNING Line {line_number}: Line ignored (no regex match, not continuation). Line='{line_strip[:100]}...'")
                        continue # Move to next line

                # --- Common Processing for Matched Lines (V1 or V2) ---
                try:
                    msg_date = parse_whatsapp_date(date_str)

                    # --- Date Check ---
                    if msg_date >= filter_start_date:
                        # --- Automation Check ---
                        # Use the enhanced is_automated_message function
                        is_auto = is_automated_message(sender_name, message_text_for_check)

                        # --- Failsafe for V2 Format ---
                        # If it matched V2 regex but wasn't caught by the function,
                        # filter it as a likely uncaught system message.
                        if is_system_format and not is_auto:
                             # print(f"  DEBUG: V2 Match ('{message_text_for_check[:50]}...') not caught by is_automated_message. Filtering as likely system message.")
                             is_auto = True

                        # --- Decision based on checks ---
                        if not is_auto:
                            current_message_is_valid = True
                        else:
                            automated_filtered_count += 1
                            current_message_is_valid = False
                    else:
                        date_filtered_count += 1
                        current_message_is_valid = False

                except ValueError as ve:
                    malformed_lines += 1
                    print(f"  WARNING Line {line_number}: Date Parse Error: {ve}. Skipping message.")
                    current_message_is_valid = False

            # --- Process the very last message block ---
            if current_message_block and current_message_is_valid:
                kept_message_blocks.append("".join(current_message_block))
                messages_kept_count += 1

    except FileNotFoundError:
        raise FileNotFoundError(f"Input file not found: {input_filepath}")
    except Exception as e:
        ln_msg = f" near line {line_number}" if line_number > 0 else ""
        raise RuntimeError(f"Error processing input file{ln_msg}: {e}")

    # --- Filtering Summary ---
    print(f"\n--- Filtering Summary ---")
    print(f"Total lines processed: {lines_processed}")
    print(f"Messages kept (within date, not automated): {messages_kept_count}")
    print(f"Messages filtered out (too old): {date_filtered_count}")
    print(f"Messages filtered out (automated/system): {automated_filtered_count}")
    print(f"Lines skipped (parse errors or unexpected format): {malformed_lines}")
    if malformed_lines > 0:
        print(f"Suggestion: Review WARNING lines above for potential format issues.")

    # --- Write Output ---
    try:
        print(f"DEBUG: Writing {messages_kept_count} messages to {output_filepath}")
        output_dir = os.path.dirname(output_filepath)
        if output_dir: os.makedirs(output_dir, exist_ok=True)

        if days_to_filter == 99999:
            prompt_days_str = "full history"; header_days_str = "All Time"
        elif days_to_filter == 30:
            prompt_days_str = "month (30 days)"; header_days_str = "Last 30 days"
        elif days_to_filter == 90:
            prompt_days_str = "3 months (90 days)"; header_days_str = "Last 90 days"
        elif days_to_filter == 7:
            prompt_days_str = "week (7 days)"; header_days_str = "Last 7 days"
        elif days_to_filter == 14:
            prompt_days_str = "2 weeks (14 days)"; header_days_str = "Last 14 days"
        else:
            prompt_days_str = f"{days_to_filter} days"; header_days_str = f"Last {days_to_filter} days"

        filtered_filename = os.path.basename(output_filepath)
        formatted_prompt = PROMPT_TEMPLATE.format(
            filtered_filename=filtered_filename, time_frame_days=prompt_days_str
        )

        with open(output_filepath, 'w', encoding='utf-8') as outfile:
            outfile.write("# --- START OF AI PROMPT ---\n")
            outfile.write(formatted_prompt)
            outfile.write("\n# --- END OF AI PROMPT ---\n\n")
            outfile.write("# --- START OF FILTERED CHAT CONTENT ---\n")
            outfile.write(f"# WhatsApp Chat Filtered Output\n")
            outfile.write(f"# Original file: {os.path.basename(input_filepath)}\n")
            outfile.write(f"# Filtered on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            filter_criteria_date = f"from {filter_start_date.strftime('%d/%m/%Y')} onwards" if days_to_filter != 99999 else "All Time"
            outfile.write(f"# Criteria: Messages {filter_criteria_date} ({header_days_str}), excluding automated/system messages.\n")
            outfile.write(f"# Kept {messages_kept_count} user messages.\n\n")

            if not kept_message_blocks:
                outfile.write("# No messages matched the filtering criteria.\n")
            else:
                output_text = ""
                for block in kept_message_blocks:
                    block_stripped = block.rstrip('\n')
                    output_text += block_stripped + '\n\n'
                outfile.write(output_text.strip() + '\n')
            outfile.write("\n# --- END OF FILTERED CHAT CONTENT ---")

    except IOError as e:
        raise IOError(f"Could not write to output file: {output_filepath}\nError: {e}")
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred during writing: {e}")

    return True, lines_processed, messages_kept_count

# --- GUI Application Class (Remains largely the same) ---
class ChatFilterApp:
    def __init__(self, master):
        self.master = master
        master.title("WhatsApp Chat Filter & Prompt Generator")
        master.geometry("600x550")

        self.style = ttk.Style()
        try: self.style.theme_use('vista')
        except tk.TclError:
            try: self.style.theme_use('clam')
            except tk.TclError: self.style.theme_use('default')

        self.zip_filepath = tk.StringVar()
        self.txt_filepath = tk.StringVar()
        self.extraction_path = tk.StringVar()
        self.extract_status = tk.StringVar()
        self.filtered_output_path = tk.StringVar()

        self.timeframe_map = {
            "Last 7 Days": 7, "Last 14 Days": 14, "Last Month (30 days)": 30,
            "Last 3 Months (90 days)": 90, "All Time (Keep All User Messages)": 99999
        }
        self.selected_timeframe = tk.StringVar(value=list(self.timeframe_map.keys())[0])

        # Frame 1: ZIP Extraction
        self.frame_zip = ttk.LabelFrame(master, text="Step 1: Select & Extract ZIP (Optional)", padding=(10, 5))
        self.frame_zip.pack(pady=5, padx=10, fill="x")
        ttk.Button(self.frame_zip, text="Select ZIP File", command=self.select_zip).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ttk.Label(self.frame_zip, textvariable=self.zip_filepath, relief="sunken", width=50, anchor='w').grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.btn_extract = ttk.Button(self.frame_zip, text="Extract ZIP Contents", command=self.extract_zip_contents, state="disabled")
        self.btn_extract.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        ttk.Label(self.frame_zip, textvariable=self.extract_status).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.frame_zip.columnconfigure(1, weight=1)

        # Frame 2: File Selection & Filtering Options
        self.frame_filter = ttk.LabelFrame(master, text="Step 2: Select TXT File & Filter Options", padding=(10, 5))
        self.frame_filter.pack(pady=5, padx=10, fill="x")
        self.btn_select_txt = ttk.Button(self.frame_filter, text="Select TXT File", command=self.select_txt_file, state="normal")
        self.btn_select_txt.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ttk.Label(self.frame_filter, textvariable=self.txt_filepath, relief="sunken", width=50, anchor='w').grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Label(self.frame_filter, text="Filter Time Frame:").grid(row=1, column=0, padx=5, pady=10, sticky="e")
        self.time_combo = ttk.Combobox(self.frame_filter, textvariable=self.selected_timeframe,
                                       values=list(self.timeframe_map.keys()), state="readonly", width=30)
        self.time_combo.grid(row=1, column=1, padx=5, pady=10, sticky="w")
        self.btn_filter = ttk.Button(self.frame_filter, text="Filter Selected File", command=self.run_filter_on_selected, state="disabled")
        self.btn_filter.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        self.frame_filter.columnconfigure(1, weight=1)

        # Frame 3: Prompt Generation
        self.frame_prompt = ttk.LabelFrame(master, text="Step 3: Generated Prompt (Also saved in output file)", padding=(10, 5))
        self.frame_prompt.pack(pady=5, padx=10, fill="both", expand=True)
        self.prompt_scrollbar_y = ttk.Scrollbar(self.frame_prompt, orient="vertical")
        self.prompt_scrollbar_x = ttk.Scrollbar(self.frame_prompt, orient="horizontal")
        self.prompt_display = tk.Text(self.frame_prompt, height=10, wrap=tk.NONE,
                                      state="disabled", borderwidth=1, relief="sunken",
                                      yscrollcommand=self.prompt_scrollbar_y.set,
                                      xscrollcommand=self.prompt_scrollbar_x.set)
        self.prompt_scrollbar_y.config(command=self.prompt_display.yview)
        self.prompt_scrollbar_x.config(command=self.prompt_display.xview)
        self.prompt_scrollbar_y.pack(side="right", fill="y")
        self.prompt_scrollbar_x.pack(side="bottom", fill="x")
        self.prompt_display.pack(side="left", fill="both", expand=True)
        self.btn_copy_prompt = ttk.Button(master, text="Copy Prompt to Clipboard", command=self.copy_prompt, state="disabled")
        self.btn_copy_prompt.pack(pady=10, padx=10, fill="x")

    def select_zip(self):
        filepath = filedialog.askopenfilename(
            title="Select WhatsApp Chat Export ZIP File",
            filetypes=[("Zip archives", "*.zip"), ("All files", "*.*")]
        )
        if filepath:
            self.zip_filepath.set(filepath)
            self.btn_extract.config(state="normal")
            self.txt_filepath.set("")
            self.extract_status.set("ZIP selected. Ready to extract.")
            self.extraction_path.set("")
            self.filtered_output_path.set("")
            self.btn_filter.config(state="disabled")
            self._clear_prompt_display()
            self.btn_copy_prompt.config(state="disabled")

    def _clear_prompt_display(self):
        try:
            self.prompt_display.config(state="normal")
            self.prompt_display.delete('1.0', tk.END)
            self.prompt_display.config(state="disabled")
        except tk.TclError: print("Warning: Could not clear prompt display.")

    def extract_zip_contents(self):
        zip_path = self.zip_filepath.get()
        if not zip_path: return
        try:
            base_dir = os.path.dirname(zip_path)
            extract_to = os.path.join(base_dir, EXTRACTION_SUBFOLDER)
        except Exception:
             try: script_dir = os.path.dirname(os.path.abspath(__file__))
             except NameError: script_dir = os.getcwd()
             extract_to = os.path.join(script_dir, EXTRACTION_SUBFOLDER)

        self.extraction_path.set(extract_to)
        self.extract_status.set("Extracting...")
        self.master.update_idletasks()
        try:
            if os.path.isdir(extract_to):
                print(f"Clearing previous contents from {extract_to}...")
                try: shutil.rmtree(extract_to)
                except Exception as e: print(f"Warning: Could not remove previous extraction: {e}")
            os.makedirs(extract_to, exist_ok=True)

            txt_found = False
            with zipfile.ZipFile(zip_path, 'r') as zf:
                print(f"Extracting all contents to: {extract_to}")
                zf.extractall(path=extract_to)
                for item in os.listdir(extract_to):
                    if item.lower().endswith(".txt"):
                        self.txt_filepath.set(os.path.join(extract_to, item))
                        print(f"Auto-selected TXT file: {item}")
                        txt_found = True; break
            if not txt_found: raise ValueError("No '.txt' file found in extracted contents.")

            self.extract_status.set(f"Extracted & TXT selected from '{os.path.basename(extract_to)}'. Ready to filter.")
            self.btn_extract.config(state="disabled")
            self.btn_filter.config(state="normal")
        except (zipfile.BadZipFile, ValueError, OSError) as e:
            self.extract_status.set(f"Error: {e}")
            messagebox.showerror("Extraction Error", str(e))
            self.btn_extract.config(state="normal")
            self.txt_filepath.set("")
            self.btn_filter.config(state="disabled")
        except Exception as e:
            self.extract_status.set("Error during extraction.")
            messagebox.showerror("Extraction Error", f"An unexpected error occurred:\n{e}")
            self.btn_extract.config(state="normal")
            self.txt_filepath.set("")
            self.btn_filter.config(state="disabled")

    def select_txt_file(self):
        initial_dir = self.extraction_path.get() or os.path.dirname(self.zip_filepath.get() or ".")
        if not os.path.isdir(initial_dir): initial_dir = "."
        filepath = filedialog.askopenfilename(
            title="Select the WhatsApp Chat TXT File", initialdir=initial_dir,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filepath:
            self.txt_filepath.set(filepath)
            self.btn_filter.config(state="normal")
            self.filtered_output_path.set("")
            self._clear_prompt_display()
            self.btn_copy_prompt.config(state="disabled")
            if self.extract_status.get().startswith("Extracted"):
                self.extract_status.set("Extraction folder used. TXT selected manually.")
            elif not self.zip_filepath.get():
                 self.extract_status.set("TXT file selected.")

    def run_filter_on_selected(self):
        input_txt = self.txt_filepath.get()
        timeframe_str_selected = self.selected_timeframe.get()
        if not input_txt or not os.path.exists(input_txt):
            messagebox.showerror("Error", "Selected TXT file not found or not selected.")
            return
        if not timeframe_str_selected:
            messagebox.showerror("Error", "Please select a time frame.")
            return
        days_to_filter = self.timeframe_map.get(timeframe_str_selected)
        if days_to_filter is None:
            messagebox.showerror("Error", "Invalid time frame selected.")
            return

        try: # Generate Output Filename
            output_dir = os.path.dirname(input_txt)
            base_name = os.path.basename(input_txt)
            name_part, ext = os.path.splitext(base_name)
            if "days" in timeframe_str_selected: time_label = f"{days_to_filter}d"
            elif "Month" in timeframe_str_selected: time_label = "30d"
            elif "3 Months" in timeframe_str_selected: time_label = "90d"
            elif "All Time" in timeframe_str_selected: time_label = "all"
            else: time_label = str(days_to_filter)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"{name_part}_filtered_{time_label}_{timestamp}{ext}"
            output_filepath = os.path.join(output_dir, output_filename)
            self.filtered_output_path.set(output_filepath)
        except Exception as e:
            messagebox.showerror("Error", f"Could not determine output file path: {e}")
            self.filtered_output_path.set(""); return

        filter_success = False
        messages_kept = 0
        lines_processed = 0
        try: # Run Filtering
            print("-" * 30); print(f"Starting filtering process...")
            print(f"Input: {input_txt}"); print(f"Filtering for: {timeframe_str_selected} ({days_to_filter} days)")
            print(f"Output to: {output_filepath}")
            self.master.config(cursor="watch"); self.master.update_idletasks()
            filter_success, lines_processed, messages_kept = filter_whatsapp_chat(
                input_txt, output_filepath, days_to_filter
            )
        except (FileNotFoundError, IOError, RuntimeError, ValueError) as e:
            error_msg = f"An error occurred during filtering:\n\n{e}"; print(f"ERROR: {error_msg}")
            messagebox.showerror("Filtering Error", error_msg)
        except Exception as e:
            error_msg = f"An unexpected error occurred during filtering:\n\n{e}"; print(f"ERROR: {error_msg}")
            messagebox.showerror("Unexpected Error", error_msg)
        finally: self.master.config(cursor="")

        if filter_success: # Post-Filtering Actions
            self.generate_and_display_prompt(days_to_filter, os.path.basename(output_filepath))
            info_title = "Success" if messages_kept > 0 else "Filtering Complete"
            time_desc = timeframe_str_selected.replace(" (Keep All User Messages)", "")
            criteria_desc = f"{time_desc}, non-automated/system"
            info_message = (f"Chat filtering finished!\n\nProcessed {lines_processed} lines.\n"
                            f"Kept {messages_kept} user messages matching criteria ({criteria_desc}).\n\n"
                            f"Filtered output (with AI prompt at top) saved to:\n{output_filepath}\n\n"
                            f"Generated prompt is also shown below.")
            if messages_kept == 0:
                info_message += "\n\n(No user messages matched criteria, but the output file was created.)"
                messagebox.showwarning(info_title, info_message)
            else: messagebox.showinfo(info_title, info_message)
        else:
            self.filtered_output_path.set("")
            self._set_prompt_display_text("Filtering failed. Cannot generate prompt.")
            self.btn_copy_prompt.config(state="disabled")

    def _set_prompt_display_text(self, text):
         try:
             self.prompt_display.config(state="normal"); self.prompt_display.delete('1.0', tk.END)
             self.prompt_display.insert('1.0', text); self.prompt_display.config(state="disabled")
         except tk.TclError: print("Warning: Could not update prompt display.")

    def generate_and_display_prompt(self, num_days, filtered_filename):
        output_path = self.filtered_output_path.get()
        if not output_path:
             self._set_prompt_display_text("Error: Filtered output path missing."); self.btn_copy_prompt.config(state="disabled")
             return

        if num_days == 99999: prompt_days_str = "full history"
        elif num_days == 30: prompt_days_str = "month (30 days)"
        elif num_days == 90: prompt_days_str = "3 months (90 days)"
        elif num_days == 7: prompt_days_str = "week (7 days)"
        elif num_days == 14: prompt_days_str = "2 weeks (14 days)"
        else: prompt_days_str = f"{num_days} days"

        try:
            prompt_text = PROMPT_TEMPLATE.format(
                filtered_filename=filtered_filename, time_frame_days=prompt_days_str
            )
            self._set_prompt_display_text(prompt_text)
            self.btn_copy_prompt.config(state="normal")
        except Exception as e:
             print(f"Error generating or displaying prompt: {e}")
             self._set_prompt_display_text(f"Error generating prompt: {e}")
             self.btn_copy_prompt.config(state="disabled")

    def copy_prompt(self):
        prompt_text = ""
        try: prompt_text = self.prompt_display.get('1.0', tk.END).strip()
        except tk.TclError: messagebox.showwarning("Copy Error", "Could not read prompt."); return

        if prompt_text and not prompt_text.startswith("Error:") and not prompt_text.startswith("Filtering failed"):
            try:
                self.master.clipboard_clear(); self.master.clipboard_append(prompt_text)
                print("Prompt copied to clipboard.")
                original_text = self.btn_copy_prompt.cget("text")
                self.btn_copy_prompt.config(text="Copied!", state="disabled")
                self.master.after(1500, lambda: self.btn_copy_prompt.config(text=original_text, state="normal"))
            except tk.TclError: messagebox.showwarning("Copy Error", "Could not access clipboard.")
            except Exception as e: messagebox.showerror("Copy Error", f"Unexpected error during copy:\n{e}")
        elif not prompt_text: messagebox.showwarning("Copy Info", "No prompt text to copy.")
        else: messagebox.showwarning("Copy Info", "Cannot copy error messages.")

# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = ChatFilterApp(root)
    root.mainloop()
# --- END OF FULL SCRIPT ---
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
    # Prioritize the format seen in the example
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
    # If loop finishes without returning, no format matched
    raise ValueError(f"Date '{date_str}' did not match any known formats: {formats_to_try}")


def is_automated_message(sender_name, message_content):
    """Checks if a message is likely an automated system message based on content patterns."""
    lower_content = message_content.lower().strip().replace('\u200e', '') # Normalize: lowercase, strip whitespace, remove LRM
    normalized_sender = sender_name.strip().replace('\u200e', '') # Normalize sender name

    # --- Content-Based Checks ---

    # Exact system message text (or very close variations)
    exact_phrases = [
        "this message was deleted",
        "this reply was deleted.", # From example
        "missed voice call",
        "missed video call",
        "started a call",
        "messages and calls are end-to-end encrypted. no one outside of this chat, not even whatsapp, can read or listen to them.",
        "messages and calls are end-to-end encrypted.",
        "created the poll:",
        "you created this community",
        "you created this group",
        "‎image omitted", # Common pattern for omitted media
        "‎video omitted",
        "‎audio omitted",
        "‎sticker omitted",
        "‎gif omitted",
        "‎document omitted",
        "‎contact omitted",
        "‎location omitted",
        "poll:", # Start of a poll message maybe?
        # Add other language variations if needed
    ]
    if lower_content in exact_phrases or (lower_content.startswith("[") and lower_content.endswith(" omitted]")):
        # print(f"  DEBUG (is_automated): Filtered by exact phrase/omitted: '{lower_content[:50]}...'")
        return True

    # Join/Leave messages (often includes sender name or number in the message body)
    join_leave_phrases = [
        "joined using this community's invite link", # From example
        "joined using this group's invite link",
        "added", # Usually followed by user names
        "removed", # Usually followed by user names
        "left", # From example
    ]
    # Check if the message *is* one of these phrases, potentially preceded by a name/number
    # Example: "+44 1234 567890 joined using this community's invite link"
    # Example: "~ John Stones left"
    if any(phrase in lower_content for phrase in join_leave_phrases):
        # More specific checks to avoid filtering actual conversation ABOUT joining/leaving
        if lower_content.endswith(" left"):
            # print(f"  DEBUG (is_automated): Filtered by content ends with ' left': '{lower_content[:50]}...'")
            return True
        if "joined using this" in lower_content and "invite link" in lower_content:
            # print(f"  DEBUG (is_automated): Filtered by content 'joined using...invite link': '{lower_content[:50]}...'")
            return True
        # Adding/Removing checks (often includes 'by')
        if (" was added by " in lower_content) or (" was removed by " in lower_content):
            # print(f"  DEBUG (is_automated): Filtered by content 'was added/removed by': '{lower_content[:50]}...'")
            return True
        # Added check for "~ user was added" style messages (as seen in provided example)
        if normalized_sender.startswith("~") and " was added" in lower_content:
            # print(f"  DEBUG (is_automated): Filtered by '~ User was added' pattern: '{lower_content[:50]}...'")
            return True
        # Simpler add/remove where the actor is the sender
        if lower_content.startswith("added ") or lower_content.startswith("removed "):
             # Check if the rest looks like names/numbers, less reliable
             # Let's be cautious here to avoid over-filtering
             pass # Avoid filtering based on just "added" or "removed" at start unless more context

    # Group setting changes
    group_change_phrases = [
        "changed the subject from",
        "changed the subject to",
        "changed this group's icon",
        "changed the group description",
        "changed their phone number to a new number.",
        "changed to a new number. tap to message or add the new number.",
        "your security code with", # followed by 'changed' usually
        "created group",
        "created community",
        "you're now an admin", "you are now an admin",
        "you're no longer an admin", "you are no longer an admin"
        # Add other common admin/setting change messages
    ]
    if any(phrase in lower_content for phrase in group_change_phrases):
        # Special check for security code change which can be noisy
        if "your security code with" in lower_content and "changed" in lower_content:
             # print(f"  DEBUG (is_automated): Filtered by security code change: '{lower_content[:50]}...'")
             return True
        # Filter if other phrases are present
        if not ("your security code with" in lower_content):
             # print(f"  DEBUG (is_automated): Filtered by group change phrase: '{lower_content[:50]}...'")
             return True

    # --- Sender-Based Checks (Use with caution) ---
    # Check if sender name starts with ~ (often indicates system action participant like in 'left' messages)
    # Combined with the content checks above, this might be redundant or filter too much.
    # Let's disable this by default unless proven necessary.
    # if normalized_sender.startswith("~"):
    #     # Check if message content is also typical for these like 'left'
    #     if lower_content == "left":
    #         print(f"  DEBUG (is_automated): Filtered by sender '~ ' and content 'left'")
    #         return True

    # If none of the above matched, it's likely a user message
    # print(f"  DEBUG (is_automated): Not filtered: Sender='{normalized_sender}', Content='{lower_content[:50]}...'") # Keep for debugging non-filtered
    return False


# --- FILTERING FUNCTION WITH DEBUGGING ---
def filter_whatsapp_chat(input_filepath, output_filepath, days_to_filter):
    """
    Reads WhatsApp chat file, filters messages by date and removes automated
    messages, then writes the result to an output file. Includes DEBUG prints.
    """
    today = datetime.now().date()
    filter_start_date = today - timedelta(days=days_to_filter)
    print(f"DEBUG: Filtering messages from {filter_start_date.strftime('%d/%m/%Y')} onwards ({days_to_filter} days).")

    # --- Regex to handle various date/time formats and potential LRM character ---
    # Handles DD/MM/YYYY, MM/DD/YYYY, YYYY/MM/DD with /, -, or . separators
    # Handles HH:MM or HH:MM:SS, optional space, optional AM/PM (case insensitive)
    # Handles optional LRM (\u200e) before sender
    # Handles optional space after closing bracket and after colon
    message_start_regex = re.compile(
        r"^\["                                        # Start bracket
        r"(\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4})"          # Date group (flexible format) - Group 1
        r",\s*"                                       # Comma and space(s)
        r"(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)"     # Time group (HH:MM or HH:MM:SS, opt AM/PM) - Group 2 (case insensitive flag used later)
        r"(?:\s*(?:AM|PM))?"                          # Optional space and AM/PM OUTSIDE the capture group
        r"\s*\]"                                      # Optional space(s), closing bracket
        r"\s*(?:\u200e)?\s*"                          # Optional space(s), optional LRM, optional space(s)
        r"([^:]+?)"                                   # Sender group (non-greedy match until colon) - Group 3
        r":\s*"                                       # Colon and optional space(s)
        r"(.*)"                                       # Message group (rest of the line) - Group 4
        , re.IGNORECASE # Make AM/PM matching case insensitive
    )

    kept_message_blocks = []
    current_message_block = []
    current_message_is_valid = False # Tracks if the *current block being built* should be kept
    lines_processed = 0
    messages_kept_count = 0 # Counts distinct messages kept
    automated_filtered_count = 0
    date_filtered_count = 0
    malformed_lines = 0
    line_number = 0

    try:
        # print(f"DEBUG: Opening input file: {input_filepath}")
        with open(input_filepath, 'r', encoding='utf-8') as infile:
            for line_number, line in enumerate(infile, 1):
                lines_processed += 1
                match = message_start_regex.match(line)

                if match:
                    # --- Process the previous block before starting a new one ---
                    if current_message_block and current_message_is_valid:
                        kept_message_blocks.append("".join(current_message_block))
                        messages_kept_count += 1
                        # print(f"DEBUG: Appended valid block ending line {line_number-1}") # Debug block append

                    # --- Start processing the new message line ---
                    current_message_block = [line] # Start new block with the matched line
                    current_message_is_valid = False # Reset validity for the new block
                    date_str, time_str, sender_name_raw, message_first_line = match.groups()
                    sender_name = sender_name_raw.strip()
                    message_text_for_check = message_first_line.strip()

                    # --- DEBUG PRINT FOR MATCHED LINE ---
                    # print(f"DEBUG Line {line_number}: Matched! Date='{date_str}' Sender='{sender_name}' Text='{message_text_for_check[:60]}...'")

                    try:
                        # --- Attempt Date Parsing ---
                        msg_date = parse_whatsapp_date(date_str)
                        # print(f"  DEBUG: Parsed date: {msg_date}") # Verbose date parse debug

                        # --- Date Check ---
                        if msg_date >= filter_start_date:
                            # print(f"  DEBUG: Date is within range ({msg_date} >= {filter_start_date})")
                            # --- Automation Check ---
                            is_auto = is_automated_message(sender_name, message_text_for_check)
                            if not is_auto:
                                current_message_is_valid = True # Mark this block as potentially keepable
                                # print(f"  DEBUG: Message is NOT automated. Marking block as valid.")
                            else:
                                automated_filtered_count += 1
                                # print(f"  DEBUG: Message IS automated. Block is invalid.")
                                current_message_is_valid = False
                        else:
                            date_filtered_count += 1
                            # print(f"  DEBUG: Date is too old ({msg_date} < {filter_start_date}). Block is invalid.")
                            current_message_is_valid = False

                    except ValueError as ve:
                        malformed_lines += 1
                        print(f"  WARNING Line {line_number}: Date Parse Error: {ve}. Skipping message.")
                        current_message_is_valid = False # Discard block due to date error

                else: # Line did NOT match the message start regex
                    # This is likely a continuation line of the previous message
                    if current_message_block: # Only append if we are currently processing a block
                        if current_message_is_valid:
                            # Only append continuation lines if the block is valid so far
                            current_message_block.append(line)
                            # print(f"DEBUG Line {line_number}: Appended continuation line to valid block.")
                        # else: # Debugging non-appended lines
                            # print(f"DEBUG Line {line_number}: Continuation line ignored (block invalid). Line='{line.strip()[:80]}...'")
                    # Log unexpected non-matching lines (that aren't blank)
                    elif line.strip():
                         malformed_lines += 1
                         # Only print a few non-matches to avoid flooding
                         if malformed_lines <= 15: # Limit debug output
                              print(f"WARNING Line {line_number}: Line ignored (no regex match, not continuation). Line='{line.strip()[:100]}...'")


            # --- Process the very last message block after the loop finishes ---
            if current_message_block and current_message_is_valid:
                kept_message_blocks.append("".join(current_message_block))
                messages_kept_count += 1
                # print(f"DEBUG: Appended FINAL valid block ending line {line_number}")

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
        # print(f"DEBUG: Writing {messages_kept_count} messages to {output_filepath}")
        output_dir = os.path.dirname(output_filepath)
        if output_dir: # Create directory if it doesn't exist
             os.makedirs(output_dir, exist_ok=True)

        with open(output_filepath, 'w', encoding='utf-8') as outfile:
            outfile.write(f"# WhatsApp Chat Filtered Output\n")
            outfile.write(f"# Original file: {os.path.basename(input_filepath)}\n")
            outfile.write(f"# Filtered on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            outfile.write(f"# Criteria: Messages from {filter_start_date.strftime('%d/%m/%Y')} onwards ({days_to_filter} days), excluding automated.\n")
            outfile.write(f"# Kept {messages_kept_count} messages.\n\n")

            if not kept_message_blocks:
                outfile.write("# No messages matched the filtering criteria.\n")
            else:
                # Join blocks, ensuring proper newlines between messages
                output_text = ""
                for block in kept_message_blocks:
                    # Ensure block ends with a newline before adding next block
                    block_stripped = block.rstrip('\n')
                    output_text += block_stripped + '\n\n' # Add double newline for separation

                # Remove trailing newlines from the final string
                outfile.write(output_text.strip() + '\n')


    except IOError as e:
        raise IOError(f"Could not write to output file: {output_filepath}\nError: {e}")
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred during writing: {e}")

    # Return success and stats
    return True, lines_processed, messages_kept_count

# --- GUI Application Class (Mostly unchanged, minor adjustments) ---

class ChatFilterApp:
    def __init__(self, master):
        self.master = master
        master.title("WhatsApp Chat Filter & Prompt Generator")
        master.geometry("600x550") # Adjusted size for prompt area

        self.style = ttk.Style()
        try:
            self.style.theme_use('vista')
        except tk.TclError:
            try:
                 self.style.theme_use('clam')
            except tk.TclError:
                 self.style.theme_use('default')

        # --- Variables ---
        self.zip_filepath = tk.StringVar()
        self.txt_filepath = tk.StringVar()
        self.extraction_path = tk.StringVar()
        self.extract_status = tk.StringVar()
        self.filtered_output_path = tk.StringVar() # Store path of the filtered file

        self.timeframe_map = {"Last 7 Days": 7, "Last 14 Days": 14, "Last Month (30 days)": 30, "Last 3 Months (90 days)": 90, "All Time (Keep All)": 99999}
        self.selected_timeframe = tk.StringVar(value=list(self.timeframe_map.keys())[0]) # Default to 7 days

        # --- Layout ---
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
        # Enable TXT selection immediately, ZIP extraction is optional
        self.btn_select_txt = ttk.Button(self.frame_filter, text="Select TXT File", command=self.select_txt_file, state="normal")
        self.btn_select_txt.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ttk.Label(self.frame_filter, textvariable=self.txt_filepath, relief="sunken", width=50, anchor='w').grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        # Time Frame Dropdown
        ttk.Label(self.frame_filter, text="Filter Time Frame:").grid(row=1, column=0, padx=5, pady=10, sticky="e")
        self.time_combo = ttk.Combobox(self.frame_filter, textvariable=self.selected_timeframe,
                                       values=list(self.timeframe_map.keys()), state="readonly", width=20)
        self.time_combo.grid(row=1, column=1, padx=5, pady=10, sticky="w")
        # Filter Button (Initially disabled until TXT is selected)
        self.btn_filter = ttk.Button(self.frame_filter, text="Filter Selected File", command=self.run_filter_on_selected, state="disabled")
        self.btn_filter.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        self.frame_filter.columnconfigure(1, weight=1)

        # Frame 3: Prompt Generation
        self.frame_prompt = ttk.LabelFrame(master, text="Step 3: Generated Prompt for AI", padding=(10, 5))
        self.frame_prompt.pack(pady=5, padx=10, fill="both", expand=True)
        # Text Area with Scrollbar
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
        # Copy Button
        self.btn_copy_prompt = ttk.Button(master, text="Copy Prompt to Clipboard", command=self.copy_prompt, state="disabled")
        self.btn_copy_prompt.pack(pady=10, padx=10, fill="x")

    def select_zip(self):
        """Opens file dialog to select ZIP file."""
        filepath = filedialog.askopenfilename(
            title="Select WhatsApp Chat Export ZIP File",
            filetypes=[("Zip archives", "*.zip"), ("All files", "*.*")]
        )
        if filepath:
            self.zip_filepath.set(filepath)
            self.btn_extract.config(state="normal")
            # Reset downstream steps if a new ZIP is selected
            self.txt_filepath.set("")
            self.extract_status.set("ZIP selected. Ready to extract.")
            self.extraction_path.set("")
            self.filtered_output_path.set("")
            # Keep TXT select enabled, but disable filter until TXT selected again
            self.btn_filter.config(state="disabled")
            self._clear_prompt_display()
            self.btn_copy_prompt.config(state="disabled")

    def _clear_prompt_display(self):
        """Helper to safely clear the prompt Text widget."""
        try:
            self.prompt_display.config(state="normal")
            self.prompt_display.delete('1.0', tk.END)
            self.prompt_display.config(state="disabled")
        except tk.TclError:
             print("Warning: Could not clear prompt display (already destroyed?).")

    def extract_zip_contents(self):
        """Extracts the contents of the selected ZIP file."""
        zip_path = self.zip_filepath.get()
        if not zip_path: return

        try:
            # Use directory of the ZIP file as the base for the extraction folder
            base_dir = os.path.dirname(zip_path)
            extract_to = os.path.join(base_dir, EXTRACTION_SUBFOLDER)
        except Exception:
            # Fallback if path parsing fails
             try: script_dir = os.path.dirname(os.path.abspath(__file__))
             except NameError: script_dir = os.getcwd()
             extract_to = os.path.join(script_dir, EXTRACTION_SUBFOLDER)

        self.extraction_path.set(extract_to)
        self.extract_status.set("Extracting...")
        self.master.update_idletasks()

        try:
            # Clear previous extraction if it exists
            if os.path.isdir(extract_to):
                print(f"Clearing previous contents from {extract_to}...")
                try:
                    shutil.rmtree(extract_to)
                except Exception as e:
                    print(f"Warning: Could not completely remove previous extraction folder: {e}")
            os.makedirs(extract_to, exist_ok=True) # Recreate after clearing or if it wasn't there

            txt_found = False
            with zipfile.ZipFile(zip_path, 'r') as zf:
                print(f"Extracting all contents to: {extract_to}")
                zf.extractall(path=extract_to)
                # Check if a txt file was actually extracted
                for item in os.listdir(extract_to):
                    if item.lower().endswith(".txt"):
                        txt_found = True
                        break # Found at least one

            if not txt_found:
                 raise ValueError("No '.txt' file found within the extracted contents.")

            self.extract_status.set(f"Extracted to '{os.path.basename(extract_to)}'. Select TXT.")
            # Automatically select the extracted TXT if only one exists? Optional enhancement.
            # For now, just enable selection.
            self.btn_extract.config(state="disabled") # Disable after successful extraction

        except (zipfile.BadZipFile, ValueError, OSError) as e:
            self.extract_status.set(f"Error: {e}")
            messagebox.showerror("Extraction Error", str(e))
            self.btn_extract.config(state="normal") # Re-enable to allow retry
        except Exception as e:
            self.extract_status.set("Error during extraction.")
            messagebox.showerror("Extraction Error", f"An unexpected error occurred:\n{e}")
            self.btn_extract.config(state="normal")

    def select_txt_file(self):
        """Opens file dialog to select the TXT file."""
        # Start browsing in the extraction folder if it exists, otherwise near ZIP/script
        initial_dir = self.extraction_path.get() or os.path.dirname(self.zip_filepath.get() or ".")
        if not os.path.isdir(initial_dir): initial_dir = "." # Fallback to current dir

        filepath = filedialog.askopenfilename(
            title="Select the WhatsApp Chat TXT File",
            initialdir=initial_dir,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filepath:
            self.txt_filepath.set(filepath)
            self.btn_filter.config(state="normal") # Enable filtering now
            # Reset prompt if a new file is selected
            self.filtered_output_path.set("")
            self._clear_prompt_display()
            self.btn_copy_prompt.config(state="disabled")
            # Update extraction status to show TXT selected
            if self.extract_status.get().startswith("Extracted"):
                self.extract_status.set(f"Extracted. TXT file selected.")
            elif not self.zip_filepath.get(): # If no zip was ever selected
                 self.extract_status.set("TXT file selected.")

    def run_filter_on_selected(self):
        """Runs the filtering logic on the selected TXT file."""
        input_txt = self.txt_filepath.get()
        timeframe_str = self.selected_timeframe.get()

        if not input_txt or not os.path.exists(input_txt):
            messagebox.showerror("Error", "Selected TXT file not found or not selected.")
            return
        if not timeframe_str:
            messagebox.showerror("Error", "Please select a time frame.")
            return

        days_to_filter = self.timeframe_map.get(timeframe_str)
        if days_to_filter is None:
            messagebox.showerror("Error", "Invalid time frame selected.")
            return

        # --- Generate Output Filename ---
        try:
            # Place filtered file in the same directory as the input TXT file
            output_dir = os.path.dirname(input_txt)
            base_name = os.path.basename(input_txt)
            name_part, ext = os.path.splitext(base_name)
            # Make filename clearer
            time_label = f"{days_to_filter}d" if days_to_filter != 99999 else "all"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"{name_part}_filtered_{time_label}_{timestamp}{ext}"
            output_filepath = os.path.join(output_dir, output_filename)
            self.filtered_output_path.set(output_filepath) # Store path BEFORE filtering
        except Exception as e:
            messagebox.showerror("Error", f"Could not determine output file path: {e}")
            self.filtered_output_path.set("") # Clear if error
            return

        # --- Run Filtering ---
        filter_success = False # Flag for success
        messages_kept = 0
        lines_processed = 0
        try:
            print("-" * 30)
            print(f"Starting filtering process...")
            print(f"Input: {input_txt}")
            print(f"Filtering for: {timeframe_str} ({days_to_filter} days)")
            print(f"Output to: {output_filepath}")
            self.master.config(cursor="watch")
            self.master.update_idletasks()

            # Call the updated filtering function
            filter_success, lines_processed, messages_kept = filter_whatsapp_chat(
                input_txt, output_filepath, days_to_filter
            )

        except (FileNotFoundError, IOError, RuntimeError, ValueError) as e:
            error_msg = f"An error occurred during filtering:\n\n{e}"
            print(f"ERROR: {error_msg}")
            messagebox.showerror("Filtering Error", error_msg)
        except Exception as e:
            error_msg = f"An unexpected error occurred during filtering:\n\n{e}"
            print(f"ERROR: {error_msg}")
            messagebox.showerror("Unexpected Error", error_msg)
        finally:
             self.master.config(cursor="") # Reset cursor

        # --- Handle Post-Filtering Actions ---
        if filter_success:
            # Always generate prompt if filtering function didn't raise error
            # Use the actual number of days (even if 99999) for the prompt text
            self.generate_and_display_prompt(days_to_filter, os.path.basename(output_filepath))

            # Show message box based on whether messages were actually kept
            info_title = "Success" if messages_kept > 0 else "Filtering Complete"
            info_message = (
                f"Chat filtering finished!\n\n"
                f"Processed {lines_processed} lines.\n"
                f"Kept {messages_kept} messages matching criteria (Last {days_to_filter} days, non-automated).\n\n"
                f"Filtered output saved to:\n{output_filepath}\n\n"
                f"Generated prompt is ready below."
            )
            if messages_kept == 0:
                info_message += "\n\n(No messages matched the time frame and content criteria.)"
                messagebox.showwarning(info_title, info_message)
            else:
                 messagebox.showinfo(info_title, info_message)
        else:
            # Filtering failed (exception was caught or function returned False)
            self.filtered_output_path.set("") # Clear output path
            self._set_prompt_display_text("Filtering failed. Cannot generate prompt.")
            self.btn_copy_prompt.config(state="disabled")


    def _set_prompt_display_text(self, text):
         """Helper to safely set text in the prompt display."""
         try:
             self.prompt_display.config(state="normal")
             self.prompt_display.delete('1.0', tk.END)
             self.prompt_display.insert('1.0', text)
             self.prompt_display.config(state="disabled")
         except tk.TclError:
              print("Warning: Could not update prompt display (already destroyed?).")

    def generate_and_display_prompt(self, num_days, filtered_filename):
        """Generates the prompt and displays it in the Text widget."""
        output_path = self.filtered_output_path.get()
        if not output_path or not os.path.exists(output_path):
            # If the file doesn't exist even after "successful" filtering (e.g., zero messages kept but file created)
            # still generate a generic prompt indicating the criteria.
            if not output_path: # If path is totally missing
                self._set_prompt_display_text("Error: Filtered output path not found. Cannot generate prompt.")
                self.btn_copy_prompt.config(state="disabled")
                return
            # If path exists but maybe empty file
            print("Warning: Filtered file path exists but might be empty or inaccessible. Generating generic prompt.")


        # Use the actual number of days requested for the prompt text
        # Use a large number like 10000 if 'All Time' was selected, for the prompt text
        prompt_days = num_days if num_days != 99999 else 10000

        try:
            # Use the generated filename in the prompt
            prompt_text = PROMPT_TEMPLATE.format(
                filtered_filename=filtered_filename,
                time_frame_days=prompt_days # Use the potentially large number here
            )
            self._set_prompt_display_text(prompt_text)
            self.btn_copy_prompt.config(state="normal") # Enable copy button
        except Exception as e:
             print(f"Error generating or displaying prompt: {e}")
             self._set_prompt_display_text(f"Error generating prompt: {e}")
             self.btn_copy_prompt.config(state="disabled")


    def copy_prompt(self):
        """Copies the generated prompt text to the clipboard."""
        prompt_text = ""
        try:
            prompt_text = self.prompt_display.get('1.0', tk.END).strip()
        except tk.TclError:
             messagebox.showwarning("Copy Error", "Could not read prompt from display.")
             return

        if prompt_text and not prompt_text.startswith("Error:") and not prompt_text.startswith("Filtering failed"):
            try:
                self.master.clipboard_clear()
                self.master.clipboard_append(prompt_text)
                print("Prompt copied to clipboard.")
                # Visual feedback
                original_text = self.btn_copy_prompt.cget("text")
                self.btn_copy_prompt.config(text="Copied!", state="disabled")
                self.master.after(1500, lambda: self.btn_copy_prompt.config(text=original_text, state="normal"))
            except tk.TclError:
                 messagebox.showwarning("Copy Error", "Could not access clipboard.")
            except Exception as e:
                 messagebox.showerror("Copy Error", f"An unexpected error occurred during copy:\n{e}")
        elif not prompt_text:
             messagebox.showwarning("Copy Info", "No prompt text generated to copy.")
        else: # Handle case where prompt display shows an error message
            messagebox.showwarning("Copy Info", "Cannot copy error messages.")


# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = ChatFilterApp(root)
    root.mainloop()
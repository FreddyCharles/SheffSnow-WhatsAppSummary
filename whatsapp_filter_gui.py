import re
from datetime import datetime, timedelta
import os
import tkinter as tk
from tkinter import filedialog, messagebox

# --- Core Filtering Logic (slightly modified for better integration) ---

def parse_whatsapp_date(date_str):
    """Parses a DD/MM/YYYY string to a date object."""
    return datetime.strptime(date_str, "%d/%m/%Y").date()

def is_automated_message(sender_name, message_content):
    """Checks if a message is an automated system message."""
    action_phrases = [
        "joined", "left", "added", "removed", "created this group",
        "created group", "changed the subject", "changed this group's icon",
        "changed their phone number to a new number.",
        "joined using this community's invite link", "was added", "was removed",
        # Add potentially missing ones if needed
        "Your security code with", # Example of another type
        "Messages and calls are end-to-end encrypted.", # Encryption notice often present
    ]

    # Check for the common pattern: \u200eSender Name action
    expected_prefix = f"\u200e{sender_name}"
    if message_content.startswith(expected_prefix):
        action_part = message_content[len(expected_prefix):].strip()
        if any(action_part == phrase or action_part.startswith(phrase + " ") for phrase in action_phrases):
             return True

    # Check for simpler system messages without the repeated name pattern
    # Important: These are often *not* preceded by a sender name and colon,
    # so this check might need refinement depending on exact export format variations.
    # The main regex usually filters these out anyway if they don't match the pattern.
    # Example: Check if message_content *itself* is an action phrase (less likely for join/left)
    if any(message_content == phrase for phrase in action_phrases):
        return True
    if "Messages and calls are end-to-end encrypted." in message_content:
        return True
    if "security code" in message_content and ("changed" in message_content or "with" in message_content):
        return True


    return False

def filter_whatsapp_chat(input_filepath, output_filepath):
    """
    Reads a WhatsApp chat file, filters messages, and writes to an output file.
    Returns True on success, False on failure.
    Raises exceptions for specific file errors.
    """
    today = datetime.now().date()
    seven_days_ago = today - timedelta(days=7)

    # Regex: [DD/MM/YYYY, HH:MM:SS<special_space>AM/PM] Sender Name: Message
    message_start_regex = re.compile(
        r"^\[(\d{2}/\d{2}/\d{4}),\s*([^\]]+?)\]\s*([^:]+?):\s*(.*)"
    )

    kept_message_blocks = []
    current_message_block = []
    current_message_is_valid = False
    lines_processed = 0
    messages_kept = 0

    try:
        with open(input_filepath, 'r', encoding='utf-8') as infile:
            for line_number, line in enumerate(infile, 1):
                lines_processed += 1
                match = message_start_regex.match(line)
                if match:
                    # Process previous block
                    if current_message_block and current_message_is_valid:
                        kept_message_blocks.append("".join(current_message_block))
                        messages_kept += 1

                    # Reset for new message
                    current_message_block = []
                    current_message_is_valid = False

                    date_str = match.group(1)
                    sender_name = match.group(3).strip()
                    message_first_line = match.group(4) # Keep potential trailing newline

                    try:
                        msg_date = parse_whatsapp_date(date_str)
                        # Check date first
                        if msg_date >= seven_days_ago:
                             # Then check if it's an automated message
                             # Use strip() only for the check, not for storing the line
                            if not is_automated_message(sender_name, message_first_line.strip()):
                                current_message_is_valid = True
                                current_message_block.append(line)
                            # else: Debug: print(f"Filtered automated: {line.strip()}")
                        # else: Debug: print(f"Filtered date: {line.strip()}")

                    except ValueError:
                        # Handle lines that look like message starts but have bad dates
                        # print(f"Warning: Bad date format on line {line_number}")
                        current_message_is_valid = False # Ensure block is discarded
                        current_message_block = []
                else:
                    # Continuation line
                    if current_message_block and current_message_is_valid:
                        current_message_block.append(line)

            # Process the very last message block after loop
            if current_message_block and current_message_is_valid:
                kept_message_blocks.append("".join(current_message_block))
                messages_kept += 1

    except FileNotFoundError:
        raise FileNotFoundError(f"Input file not found: {input_filepath}")
    except Exception as e:
        # Catch other potential reading/regex errors
        raise RuntimeError(f"Error processing input file: {e}")

    if not kept_message_blocks:
        # It's possible no messages match the criteria, which isn't an error,
        # but we might want to inform the user. The calling code will handle this.
        pass

    try:
        with open(output_filepath, 'w', encoding='utf-8') as outfile:
            for block in kept_message_blocks:
                outfile.write(block)
    except IOError as e:
        raise IOError(f"Could not write to output file: {output_filepath}\nError: {e}")
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred during writing: {e}")

    return True, lines_processed, messages_kept # Indicate success

# --- GUI Interaction ---

def run_filter_process():
    # Hide the main tkinter window
    root = tk.Tk()
    root.withdraw()

    # Ask user to select the input WhatsApp chat file
    input_filepath = filedialog.askopenfilename(
        title="Select WhatsApp Chat Export File",
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
    )

    if not input_filepath:
        messagebox.showinfo("Cancelled", "No file selected. Operation cancelled.")
        return # Exit if user cancelled

    # --- Generate Output Filename ---
    try:
        input_dir = os.path.dirname(input_filepath)
        base_name = os.path.basename(input_filepath)
        name_part, ext_part = os.path.splitext(base_name)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"{name_part}_filtered_{timestamp}{ext_part}"
        output_filepath = os.path.join(input_dir, output_filename)

    except Exception as e:
        messagebox.showerror("Error", f"Could not determine output file path: {e}")
        return

    # --- Run the Filtering ---
    try:
        print(f"Input file: {input_filepath}") # Log to console if visible
        print(f"Output file: {output_filepath}")

        success, lines_processed, messages_kept = filter_whatsapp_chat(input_filepath, output_filepath)

        if success:
            if messages_kept > 0:
                messagebox.showinfo("Success",
                                    f"Chat filtered successfully!\n\n"
                                    f"Processed {lines_processed} lines.\n"
                                    f"Kept {messages_kept} messages.\n\n"
                                    f"Saved to:\n{output_filepath}")
            else:
                # Technically successful, but no messages met the criteria
                messagebox.showwarning("Completed",
                                      f"Processing complete, but no messages matched the criteria (last 7 days, non-automated).\n\n"
                                      f"Processed {lines_processed} lines.\n"
                                      f"An empty file may have been created:\n{output_filepath}")
        # Note: If filter_whatsapp_chat returned False, it would have raised an exception caught below

    except (FileNotFoundError, IOError, RuntimeError) as e:
        print(f"Error: {e}") # Log error details
        messagebox.showerror("Error", f"An error occurred during processing:\n\n{e}")
    except Exception as e:
        # Catch any other unexpected errors
        print(f"Unexpected Error: {e}")
        messagebox.showerror("Unexpected Error", f"An unexpected error occurred:\n\n{e}")

# --- Main Execution ---
if __name__ == "__main__":
    run_filter_process()
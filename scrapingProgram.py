import time
import json
import os
import re
from datetime import datetime # Keep for timestamp in output filename
import tkinter as tk
from tkinter import filedialog, messagebox

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
# from selenium.webdriver.edge.service import Service as EdgeService        # Uncomment for Edge
# from selenium.webdriver.edge.options import Options as EdgeOptions      # Uncomment for Edge
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, StaleElementReferenceException
)
from webdriver_manager.chrome import ChromeDriverManager
# from webdriver_manager.microsoft import EdgeChromiumDriverManager # Uncomment for Edge


# --- Configuration ---
CHAT_NAME = "SheffSnow Announcements"  # <<< --- CHANGE THIS TO THE EXACT CHAT NAME
SCROLL_COUNT = 15                      # Number of times to scroll up (adjust as needed)
SCROLL_PAUSE_TIME = 1.5                # Seconds to wait between scrolls
WAIT_TIMEOUT = 60                      # Max seconds to wait for elements
LOGIN_TIMEOUT = 120                    # Max seconds to wait for QR scan / login
RAW_OUTPUT_FILE = "whatsapp_messages_raw.json" # Output from scraping
FILTERED_OUTPUT_FILE_SUFFIX = "_filtered"      # Suffix for the filtered file
USE_SAVED_SESSION = True               # Try reusing a session?
USER_DATA_DIR = "whatsapp_session"     # Directory for session data

# --- Locators (Check/Update these if script fails - WhatsApp Web changes often) ---
QR_CODE_SELECTOR = '[data-testid="qrcode"]'
LOGGED_IN_INDICATOR = '#pane-side' # Element indicating successful login
# Search box - using a potentially more robust XPath first, then fallback
SEARCH_XPATH_PRIMARY = '//div[contains(@class, "lexical-rich-text-input")]//p[@class="selectable-text copyable-text"][@contenteditable="true"]'
SEARCH_XPATH_FALLBACK = '//div[@contenteditable="true"][@data-tab="3"]' # Original fallback
CHAT_LINK_XPATH_TEMPLATE = f'//span[@title="{CHAT_NAME}"]' # Finds chat by title
MESSAGE_PANE_XPATH = '//div[@data-testid="conversation-panel-messages"]' # Contains messages
MESSAGE_CONTAINER_XPATH = './/div[contains(@class, "message-")]' # Individual message bubble (relative)
SENDER_NAME_XPATH = './/span[contains(@class, "sender-name")] | .//div[contains(@class, "_11JPr")]/span[@dir="auto"]' # Sender name (relative)
MESSAGE_TEXT_XPATH = './/span[contains(@class, "selectable-text")]/span' # Message text span (relative)
TIMESTAMP_XPATH = './/span[@data-testid="message-meta"]//span' # Timestamp (relative)

# --- Selenium Scraping Functions ---

def setup_driver():
    """Sets up the Selenium WebDriver."""
    options = ChromeOptions()
    # options = EdgeOptions() # Uncomment for Edge

    if USE_SAVED_SESSION:
        if not os.path.exists(USER_DATA_DIR):
            os.makedirs(USER_DATA_DIR)
        # Use absolute path for consistency
        abs_user_data_dir = os.path.abspath(USER_DATA_DIR)
        options.add_argument(f"user-data-dir={abs_user_data_dir}")
        print(f"Attempting to use session data from: {abs_user_data_dir}")
    # else: # Optional: Use incognito if not saving session
    #     options.add_argument("--incognito")

    # Standard options
    options.add_argument("--disable-extensions")
    # options.add_argument("--headless") # Run headless (no browser window) - may affect login/QR
    options.add_argument("--start-maximized")
    options.add_argument('--log-level=3') # Suppress excessive console logs from Chrome/Driver
    options.add_experimental_option('excludeSwitches', ['enable-logging']) # Suppress DevTools logs
    # options.add_experimental_option("detach", True) # Keep browser open after script finishes (for debugging)

    try:
        # Using webdriver-manager
        service = ChromeService(executable_path=ChromeDriverManager().install())
        # service = EdgeService(executable_path=EdgeChromiumDriverManager().install()) # For Edge
        driver = webdriver.Chrome(service=service, options=options)
        # driver = webdriver.Edge(service=service, options=options) # For Edge
        print("WebDriver setup successful.")
        return driver
    except Exception as e:
        print(f"Error setting up WebDriver: {e}")
        print("Please ensure you have Google Chrome (or MS Edge) installed.")
        print("If using manual webdriver, ensure it's in your PATH or path is correct.")
        return None

def wait_for_login(driver):
    """Waits for the user to log in (QR scan or session load)."""
    print("Opening WhatsApp Web...")
    driver.get("https://web.whatsapp.com")

    try:
        print("Checking for existing session...")
        # Wait briefly to see if we are logged in immediately from session data
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, LOGGED_IN_INDICATOR))
        )
        print("Logged in using saved session.")
        # Add a small delay for page elements to stabilize after session load
        time.sleep(3)
        return True
    except TimeoutException:
        print("Existing session not found or expired.")
        # Check if QR code is displayed
        try:
             WebDriverWait(driver, WAIT_TIMEOUT).until(
                 EC.presence_of_element_located((By.CSS_SELECTOR, QR_CODE_SELECTOR))
             )
             print(f"QR Code detected. Please scan within {LOGIN_TIMEOUT} seconds...")
             # Now wait for the login to complete (chat pane appears)
             WebDriverWait(driver, LOGIN_TIMEOUT).until(
                 EC.presence_of_element_located((By.CSS_SELECTOR, LOGGED_IN_INDICATOR))
             )
             print("Login successful!")
             # Add a small delay for page elements to stabilize after login
             time.sleep(5)
             return True
        except TimeoutException:
             # Handle cases where QR code doesn't appear or login takes too long
             print("Login timeout or QR code not found/scanned in time.")
             # Check again if maybe login succeeded just as timeout hit
             try:
                  driver.find_element(By.CSS_SELECTOR, LOGGED_IN_INDICATOR)
                  print("Login seems to have succeeded just after timeout check.")
                  time.sleep(3)
                  return True
             except NoSuchElementException:
                  print("Could not confirm login.")
                  return False
        except Exception as e:
            print(f"An error occurred during login wait: {e}")
            return False

def find_and_open_chat(driver):
    """Searches for and clicks on the specified chat."""
    print(f"Searching for chat: '{CHAT_NAME}'...")
    try:
        wait = WebDriverWait(driver, WAIT_TIMEOUT)

        # 1. Find the search box more reliably
        try:
            search_box = wait.until(
                EC.presence_of_element_located((By.XPATH, SEARCH_XPATH_PRIMARY))
            )
            print("Using primary search box XPath.")
        except TimeoutException:
            # Fallback to original XPath if primary one fails
            print("Primary search box XPath failed, using fallback.")
            search_box = wait.until(
                EC.presence_of_element_located((By.XPATH, SEARCH_XPATH_FALLBACK))
            )

        # Click might be needed if it's not focused
        try:
            search_box.click()
        except Exception as click_err:
            # ElementClickInterceptedException is common if something overlays it briefly
            print(f"Note: Clicking search box generated an event (often ignorable): {type(click_err).__name__}")
            # Try JS click as an alternative if normal click fails badly
            # driver.execute_script("arguments[0].click();", search_box)

        search_box.clear()
        search_box.send_keys(CHAT_NAME)
        print(f"Typed '{CHAT_NAME}' into search.")
        time.sleep(3) # Allow search results to populate and render

        # 2. Find the chat link in the results
        chat_link_xpath = CHAT_LINK_XPATH_TEMPLATE
        # Use visibility_of_element_located for better interaction readiness
        chat_link = wait.until(
             EC.visibility_of_element_located((By.XPATH, chat_link_xpath))
        )
        print("Chat found in search results.")

        # 3. Click the chat link - JS click can sometimes be more reliable
        try:
            driver.execute_script("arguments[0].click();", chat_link)
        except Exception as js_click_err:
            print(f"JS click failed ({type(js_click_err).__name__}), trying standard click.")
            # Standard click as fallback
            chat_link.click()
        print(f"Clicked on chat: '{CHAT_NAME}'.")

        # 4. Wait for the message pane of the chat to be identifiable
        wait.until(
            EC.presence_of_element_located((By.XPATH, MESSAGE_PANE_XPATH))
        )
        # Add a small delay for chat content to start loading
        time.sleep(3)
        print("Chat opened successfully.")
        return True

    except TimeoutException:
        print(f"Error: Could not find or open chat '{CHAT_NAME}' within timeout.")
        print("Possible reasons:")
        print(" - CHAT_NAME is not exact (case-sensitive).")
        print(" - Chat is not pinned or visible in the initial list, requiring scrolling.")
        print(" - WhatsApp Web interface has changed, breaking XPATH selectors.")
        print(f"   - Search Box XPATHs used: Primary='{SEARCH_XPATH_PRIMARY}', Fallback='{SEARCH_XPATH_FALLBACK}'")
        print(f"   - Chat Link XPATH used: '{CHAT_LINK_XPATH_TEMPLATE}'")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while opening chat: {e}")
        import traceback
        traceback.print_exc() # Print traceback for unexpected errors here
        return False

def scroll_up_to_load_messages(driver):
    """Scrolls up in the message pane to load older messages."""
    print(f"Scrolling up {SCROLL_COUNT} times to load messages...")
    try:
        # Locate the specific scrollable element. This is often the parent of the message pane.
        # WhatsApp uses dynamic class names, making this tricky.
        message_pane = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.XPATH, MESSAGE_PANE_XPATH))
        )

        # Try to find the parent scrollable div using JavaScript to check computed style
        # This is more robust than relying on potentially changing class names.
        scrollable_element = driver.execute_script("""
            let el = arguments[0];
            while (el) {
                // Check if the element itself or a known chat area parent is scrollable
                if (window.getComputedStyle(el).overflowY === 'scroll' || window.getComputedStyle(el).overflowY === 'auto') {
                     // Check for common class patterns or attributes of the chat scroll area
                     if (el.classList.contains('copyable-area') || el.querySelector('.copyable-area')) {
                         return el; // Found the main area container likely
                     }
                     // If it's the message pane's direct parent and scrollable, use it
                     if (el === arguments[0].parentElement) {
                         return el;
                     }
                }
                 // Check specific data-testid if style checks fail or are ambiguous
                 if (el.hasAttribute('data-testid') && el.getAttribute('data-testid') === 'conversation-panel-messages') {
                     // Check its parent specifically
                     let parent = el.parentElement;
                     if (parent && (window.getComputedStyle(parent).overflowY === 'scroll' || window.getComputedStyle(parent).overflowY === 'auto')) {
                         return parent;
                     }
                 }
                // Move up the DOM tree
                el = el.parentElement;
                // Safety break if we somehow reach the top without finding it
                if (!el || el.tagName === 'BODY' || el.tagName === 'HTML') break;
            }
            // Fallback: If JS fails, return the message pane's direct parent
            return arguments[0].parentElement;
            """, message_pane)

        if not scrollable_element:
            print("Warning: Could not automatically detect the specific scrollable element via JS. Falling back to message pane parent.")
            # Fallback to finding parent based on structure assumption
            scrollable_element = driver.find_element(By.XPATH, f'{MESSAGE_PANE_XPATH}/..') # Direct parent XPath

        print(f"Identified scrollable element: Tag='{scrollable_element.tag_name}', Class='{scrollable_element.get_attribute('class') or 'N/A'}', ID='{scrollable_element.get_attribute('id') or 'N/A'}'")

        last_scroll_height = 0
        no_change_count = 0
        stable_count = 3 # How many consecutive times height must be stable to stop early

        for i in range(SCROLL_COUNT):
            # Get current height *before* scrolling up
            current_scroll_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_element)

            # Check if height has stabilized
            if i > 0 and current_scroll_height == last_scroll_height:
                 no_change_count += 1
                 print(f"  Scroll attempt {i+1}/{SCROLL_COUNT}: Height {current_scroll_height} unchanged (Stable count: {no_change_count}/{stable_count})")
                 if no_change_count >= stable_count:
                      print("Scroll height stabilized. Stopping scroll early.")
                      break
            else:
                 no_change_count = 0 # Reset counter if height changed or first scroll
                 if i > 0: print(f"  Scroll attempt {i+1}/{SCROLL_COUNT}: Height changed: {last_scroll_height} -> {current_scroll_height}")
                 else: print(f"  Scroll attempt {i+1}/{SCROLL_COUNT}: Initial height {current_scroll_height}")


            last_scroll_height = current_scroll_height

            # Scroll to the top of the element
            driver.execute_script("arguments[0].scrollTop = 0;", scrollable_element)
            # print(f"Scroll attempt {i+1}/{SCROLL_COUNT} complete.") # Verbose logging if needed
            time.sleep(SCROLL_PAUSE_TIME) # IMPORTANT: Wait for messages to load

        print("Scrolling finished.")

    except TimeoutException:
        print("Error: Could not find the message pane for scrolling.")
    except Exception as e:
        print(f"An error occurred during scrolling: {e}")
        import traceback
        traceback.print_exc()


def scrape_messages(driver):
    """Finds message elements and extracts sender, text, and timestamp."""
    print("Starting message scraping...")
    messages_data = []
    processed_message_ids = set() # To handle potential duplicates if DOM updates
    try:
        # Wait briefly for any final messages loaded by scrolling to render
        time.sleep(2)
        message_pane = driver.find_element(By.XPATH, MESSAGE_PANE_XPATH)
        # Find elements relative to the pane to ensure they are within the correct chat
        message_elements = message_pane.find_elements(By.XPATH, MESSAGE_CONTAINER_XPATH)
        print(f"Found {len(message_elements)} potential message container elements.")

        if not message_elements:
            print(f"Warning: No message elements found with relative XPATH: {MESSAGE_CONTAINER_XPATH}")
            print(f"Check if the chat is empty or if the selector needs updating.")
            return []

        for element in message_elements:
            # Use element's internal ID as a fallback unique ID if data-id is missing
            # Note: element.id is session-specific and not persistent
            element_id = element.get_attribute('data-id') or element.id

            # Skip if we've already processed this element ID in this scrape session
            if element_id in processed_message_ids:
                continue

            try:
                # Initialize defaults
                sender = "Me/System" # Default sender if not found
                text = "[Non-text content or empty]" # Default text
                timestamp = None

                # Try extracting sender name (might not exist for all messages)
                try:
                    sender_element = element.find_element(By.XPATH, SENDER_NAME_XPATH)
                    sender = sender_element.text.strip()
                except NoSuchElementException:
                    pass # Keep default "Me/System"
                except StaleElementReferenceException:
                     print(f"Warn: Stale sender element for ID {element_id}, skipping message.")
                     continue # Skip this message if critical part is stale

                # Try extracting message text
                try:
                    text_element = element.find_element(By.XPATH, MESSAGE_TEXT_XPATH)
                    text = text_element.text.strip()
                    if not text: # Handle case where span exists but is empty
                         text = "[Empty message span]"
                except NoSuchElementException:
                     # If standard text span not found, check for image alt text
                     try:
                        img_element = element.find_element(By.TAG_NAME, "img")
                        alt_text = img_element.get_attribute('alt')
                        if alt_text:
                            text = f"[Image: {alt_text}]"
                        else:
                            text = "[Image/Media without alt text]"
                     except NoSuchElementException:
                        # Could be a sticker, video placeholder, deleted msg, etc.
                        # Keep default "[Non-text content or empty]"
                        pass
                except StaleElementReferenceException:
                     print(f"Warn: Stale text element for ID {element_id}, skipping message.")
                     continue # Skip this message

                # Try extracting timestamp
                try:
                    timestamp_element = element.find_element(By.XPATH, TIMESTAMP_XPATH)
                    timestamp = timestamp_element.text.strip()
                except NoSuchElementException:
                    pass # Keep default timestamp (None)
                except StaleElementReferenceException:
                    # Timestamp becoming stale is usually less critical, maybe log a warning
                    print(f"Warn: Stale timestamp element for ID {element_id}.")
                    pass # Keep timestamp as None

                # Add message to list if it contains meaningful text
                # (i.e., not just the placeholder for non-text/empty)
                if text and text != "[Non-text content or empty]" and text != "[Empty message span]":
                    message_info = {
                        "sender": sender,
                        "text": text,
                        "timestamp": timestamp,
                        # "element_id": element_id # Optional: uncomment for debugging IDs
                    }
                    messages_data.append(message_info)
                    processed_message_ids.add(element_id) # Mark as processed *after* successful append

            except StaleElementReferenceException:
                 # Catch staleness if the main 'element' becomes invalid during processing
                 print(f"Warn: Stale message container (ID {element_id}), skipping.")
                 continue # Skip this whole element
            except Exception as e:
                print(f"Error processing one message element (ID {element_id}): {e}")
                # Optionally print element details for debugging:
                try:
                   print(f"Problematic element HTML (outer): {element.get_attribute('outerHTML')[:200]}...")
                except: pass # Ignore errors getting outerHTML if element is gone

        print(f"Successfully scraped {len(messages_data)} messages with text/media info.")
        return messages_data

    except NoSuchElementException as e:
        print(f"Error: Could not find primary element for scraping. Check XPATH selectors.")
        print(f"Missing element likely related to: {e}")
        print(f"Message Pane XPATH: {MESSAGE_PANE_XPATH}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred during scraping: {e}")
        import traceback
        traceback.print_exc()
        return []

def save_to_json(data, filename):
    """Saves data to a JSON file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Data successfully saved to {filename}")
        return True
    except IOError as e:
        print(f"Error saving data to JSON file {filename}: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred saving JSON to {filename}: {e}")
        return False


# --- Filtering Logic (Adapted for JSON structure) ---

def is_automated_message(sender_name, message_content):
    """
    Checks if a message seems like an automated system message based on sender/content.
    This works on the data extracted from the web elements (dictionaries).
    It's heuristic and might need tuning for specific community messages.
    """
    if not message_content: # Handle empty/None messages
        return False
    # Handle None sender (should be rare if default is applied, but good practice)
    sender = sender_name if sender_name else "Me/System"
    text = message_content

    # Normalize sender name (remove potential unicode chars sometimes seen in exports)
    # Although less likely needed with direct scraping, it doesn't hurt.
    normalized_sender = sender.replace('\u200e', '').strip()
    lower_content = text.lower()

    # Phrases indicating automated actions
    action_phrases = [
        "joined", "left", "added", "removed", "created this group",
        "created group", "changed the subject", "changed this group's icon",
        "changed their phone number to a new number.", "admin", # "is now an admin", "no longer an admin"
        "joined using this community's invite link", "was added", "was removed",
        "You created group", "You changed", "You added", "You removed", "You joined",
        "changed security code", "security code changed",
        "created this community", "added you",
        "missed voice call", "missed video call",
        "This group was created", "started a call",
        "deleted this message", "This message was deleted",
        # Community specific?
        "created the announcement group", "updated the community info",
        # Encryption notice is very common
         "messages and calls are end-to-end encrypted",
         "no one outside of this chat, not even whatsapp, can read or listen to them."
    ]

    # Check 1: Common system messages (often appear without explicit sender in web view)
    # Use lower_content for case-insensitive matching
    if any(phrase in lower_content for phrase in action_phrases):
        # Be more specific for short/common words like "changed" or "admin"
        if "changed" in lower_content and ("subject" in lower_content or "icon" in lower_content or "security code" in lower_content or "phone number" in lower_content):
            return True
        if "admin" in lower_content and ("now an" in lower_content or "no longer" in lower_content):
             return True
        # Check for the full encryption message specifically
        if "messages and calls are end-to-end encrypted" in lower_content:
             return True
        # For other generic phrases, check if sender is "Me/System"
        if sender == "Me/System" and any(phrase in lower_content for phrase in ["joined", "left", "added", "removed", "created"]):
             # Likely automated if no specific sender was scraped and text contains these actions
             return True
        # If not encryption message or specific patterns, check if it's one of the simpler phrases
        if any(phrase == lower_content for phrase in ["missed voice call", "missed video call", "deleted this message"]):
             return True


    # Check 2: Patterns where sender name might be embedded in the text
    # (Less common with scraping compared to exports, but check simple cases)
    # Example: "You added John Doe" - here sender is "Me/System", text contains action.
    if sender == "Me/System":
        temp_content = text.replace('\u200e', '').strip()
        # Look for "<Name> <action_phrase>" or "You <action_phrase>"
        words = temp_content.split()
        if len(words) > 1:
            first_word = words[0].lower()
            action_part = " ".join(words[1:]).lower()
            # Check "You <action>"
            if first_word == "you" and any(action_part.startswith(p) for p in action_phrases):
                return True
            # Check "<Possibly Name> <action>" - less reliable heuristic
            # If first word is capitalized (potential name) and action follows
            # This is prone to false positives, use cautiously or disable if needed
            # if words[0][0].isupper() and any(action_part.startswith(p) for p in action_phrases):
            #    print(f"DEBUG: Potential name+action: {text}") # Debug if enabling this check
            #    return True


    # Check 3: Check based on the scraped sender name itself
    # E.g., if sender is literally "You" for actions performed by the user
    if normalized_sender.lower() == "you":
         if any(phrase in lower_content for phrase in action_phrases):
              # Example: Sender = "You", Text = "You created group..."
              return True

    # If none of the above rules triggered, assume it's a user message
    return False


def filter_scraped_json_data(input_data):
    """
    Filters a list of message dictionaries (from scraped JSON).
    Removes messages identified as automated/system using `is_automated_message`.
    Date filtering is NOT performed due to scraped timestamp limitations.
    Returns the filtered list and counts.
    """
    if not isinstance(input_data, list):
        # Ensure input is a list before iterating
        print("Error: Input data for filtering is not a list.")
        return [], 0, 0 # Return empty list and zero counts

    filtered_messages = []
    messages_processed_count = 0
    messages_kept_count = 0
    messages_removed_count = 0

    for msg in input_data:
        messages_processed_count += 1
        # Use .get() for safe access, provide defaults
        sender = msg.get("sender", "Me/System")
        text = msg.get("text", "")

        if not is_automated_message(sender, text):
            filtered_messages.append(msg)
            messages_kept_count += 1
        else:
            messages_removed_count += 1
            # Debug print (optional - can be very verbose)
            # print(f"Filtered out: Sender='{sender}', Text='{text[:60]}...'")

    print(f"Filtering complete. Processed: {messages_processed_count}, Kept: {messages_kept_count}, Removed: {messages_removed_count}")
    return filtered_messages, messages_processed_count, messages_kept_count


# --- GUI Interaction for Filtering ---

def run_filter_process_gui():
    """Launches a GUI to select a scraped JSON file and filter it."""
    root = tk.Tk()
    root.withdraw() # Hide the main tkinter window

    # Ask user to select the *input JSON* file
    input_filepath = filedialog.askopenfilename(
        title="Select Scraped WhatsApp JSON File to Filter",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
    )

    if not input_filepath:
        messagebox.showinfo("Cancelled", "No file selected. Filtering cancelled.")
        return

    # --- Generate Output Filename ---
    try:
        input_dir = os.path.dirname(input_filepath)
        base_name = os.path.basename(input_filepath)
        name_part, ext_part = os.path.splitext(base_name)

        # Ensure extension is .json for output
        output_ext = ".json"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Add suffix before the extension
        output_filename = f"{name_part}{FILTERED_OUTPUT_FILE_SUFFIX}_{timestamp}{output_ext}"
        output_filepath = os.path.join(input_dir, output_filename)

    except Exception as e:
        messagebox.showerror("Error", f"Could not determine output file path: {e}")
        return

    # --- Run the Filtering ---
    try:
        print(f"Filtering input JSON: {input_filepath}")
        print(f"Filtered output JSON: {output_filepath}")

        # 1. Read the input JSON
        with open(input_filepath, 'r', encoding='utf-8') as f:
            scraped_data = json.load(f)

        # 2. Filter the data (applies automated message filter only)
        filtered_data, processed_count, kept_count = filter_scraped_json_data(scraped_data)

        # 3. Save the filtered data
        if save_to_json(filtered_data, output_filepath):
            if kept_count > 0:
                messagebox.showinfo("Success",
                                    f"JSON data filtered successfully!\n"
                                    f"(Automated system messages removed. Date filtering was not applied.)\n\n"
                                    f"Processed {processed_count} messages.\n"
                                    f"Kept {kept_count} messages.\n\n"
                                    f"Saved to:\n{output_filepath}")
            else:
                 # Handle case where filtering removed all messages
                 messagebox.showwarning("Completed",
                                       f"Filtering complete, but no messages remained after removing automated ones.\n\n"
                                       f"Processed {processed_count} messages.\n"
                                       f"An empty list was saved to:\n{output_filepath}")
        else:
            # save_to_json would have printed an error, show dialog too
             messagebox.showerror("Error", f"Failed to save filtered data to:\n{output_filepath}\n\nCheck console output for details.")


    except FileNotFoundError:
        messagebox.showerror("Error", f"Input JSON file not found:\n{input_filepath}")
    except json.JSONDecodeError:
        messagebox.showerror("Error", f"Invalid JSON format in file:\n{input_filepath}\n\nCannot process this file.")
    except (IOError, TypeError, RuntimeError) as e:
        # Catch specific errors from filtering or file handling
        print(f"Error during filtering process: {e}")
        messagebox.showerror("Error", f"An error occurred during filtering:\n\n{e}")
    except Exception as e:
        # Catch any other unexpected errors
        print(f"Unexpected Error during filtering: {e}")
        import traceback
        traceback.print_exc() # Log unexpected errors fully
        messagebox.showerror("Unexpected Error", f"An unexpected error occurred:\n\n{e}")


# --- Main Execution ---
if __name__ == "__main__":
    start_time = time.time()
    driver = None
    raw_data_saved = False
    try:
        # --- Part 1: Scraping ---
        print("--- Starting WhatsApp Scraper ---")
        driver = setup_driver()
        if driver:
            if wait_for_login(driver):
                if find_and_open_chat(driver):
                    scroll_up_to_load_messages(driver)
                    scraped_data = scrape_messages(driver)

                    if scraped_data:
                        # Save the raw scraped data
                        if save_to_json(scraped_data, RAW_OUTPUT_FILE):
                             raw_data_saved = True
                        else:
                             print(f"Warning: Failed to save raw scraped data to {RAW_OUTPUT_FILE}")
                    else:
                        print("No messages were scraped or extracted. No raw data file created.")
                else:
                    print("Could not open the target chat. Exiting scraping part.")
            else:
                print("Login failed or timed out. Exiting scraping part.")
        else:
            print("WebDriver setup failed. Cannot start scraping.")

    except Exception as e:
        print(f"\n--- An Critical Error Occurred During Scraping ---")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Details: {e}")
        import traceback
        traceback.print_exc() # Print full traceback for critical scraping errors

    finally:
        # Ensure WebDriver is closed even if errors occur during scraping
        if driver:
            print("Closing WebDriver...")
            try:
                driver.quit()
                print("WebDriver closed.")
            except Exception as quit_err:
                print(f"Error occurred while quitting WebDriver: {quit_err}")

    # --- Part 2: Optional Filtering via GUI ---
    if raw_data_saved:
         print("\n--- Scraping finished ---")
         print(f"Raw data saved to: {RAW_OUTPUT_FILE}")
         print("Launching filter tool...")
         # Run the GUI process AFTER the driver is closed
         run_filter_process_gui()

    elif os.path.exists(RAW_OUTPUT_FILE):
         # Handle case where scraping failed this time, but a previous raw file exists
         print("\n--- Scraping did not complete successfully or save new data this time ---")
         print(f"An existing raw data file was found: {RAW_OUTPUT_FILE}")
         user_choice = input("Do you want to try filtering this existing file? (y/n): ").lower()
         if user_choice == 'y':
             print("Launching filter tool for existing file...")
             run_filter_process_gui()
         else:
             print("Filtering step skipped.")
    else:
         print("\n--- Scraping did not complete successfully and no raw data file was found. ---")
         print("Cannot proceed to filtering.")

    end_time = time.time()
    print(f"\nScript finished in {end_time - start_time:.2f} seconds.")

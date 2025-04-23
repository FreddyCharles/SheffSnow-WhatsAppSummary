
import time
import json
import os
import re # Added for filtering
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
# from selenium.webdriver.edge.service import Service as EdgeService
# from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, StaleElementReferenceException
)
from webdriver_manager.chrome import ChromeDriverManager
# from webdriver_manager.microsoft import EdgeChromiumDriverManager

# --- Configuration ---
CHAT_NAME = "SheffSnow Announcements"  # <<< --- CHANGE THIS TO THE EXACT CHAT NAME
SCROLL_COUNT = 15  # Number of times to scroll up (adjust as needed)
SCROLL_PAUSE_TIME = 1.5 # Seconds to wait between scrolls for content loading
WAIT_TIMEOUT = 60  # Max seconds to wait for elements to appear
LOGIN_TIMEOUT = 120 # Max seconds to wait for QR code scan / login
# Output file will now contain FILTERED messages
OUTPUT_FILE = "whatsapp_messages_filtered.json"
USE_SAVED_SESSION = True # Set to True to try reusing a session
USER_DATA_DIR = "whatsapp_session" # Directory to store session data

# --- Locators (These might change if WhatsApp updates its web interface) ---
# (Locators remain the same as the previous script)
QR_CODE_SELECTOR = '[data-testid="qrcode"]'
LOGGED_IN_INDICATOR = '#pane-side'
SEARCH_BOX_XPATH = '//div[@contenteditable="true"][@data-tab="3"]'
CHAT_LINK_XPATH_TEMPLATE = f'//span[@title="{CHAT_NAME}"]'
MESSAGE_PANE_XPATH = '//div[@data-testid="conversation-panel-messages"]'
MESSAGE_CONTAINER_XPATH = './/div[contains(@class, "message-")]'
SENDER_NAME_XPATH = './/span[contains(@class, "sender-name")] | .//div[contains(@class, "_11JPr")]/span[@dir="auto"]'
MESSAGE_TEXT_XPATH = './/span[contains(@class, "selectable-text")]/span'
TIMESTAMP_XPATH = './/span[@data-testid="message-meta"]//span'

# --- Filtering Logic (Adapted for Scraped Data) ---

def is_automated_message(sender_name, message_content):
    """
    Checks if a message seems like an automated system message based on sender/content.
    Note: This works on the data extracted from the web elements.
    """
    if not message_content: # Handle empty messages if they occur
        return False
    if not sender_name: # Handle cases where sender might be None
        sender_name = "" # Treat as empty string for checks

    # Normalize sender name --- Imports ---
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
# from selenium.webdriver.edge.service import Service as EdgeService
# from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, StaleElementReferenceException
)
from webdriver_manager.chrome import ChromeDriverManager
# from webdriver_manager.microsoft import EdgeChromiumDriverManager


# --- Configuration ---
CHAT_NAME = "SheffSnow Announcements"  # <<< --- CHANGE THIS TO THE EXACT CHAT NAME
SCROLL_COUNT = 15
SCROLL_PAUSE_TIME = 1.5
WAIT_TIMEOUT = 60
LOGIN_TIMEOUT = 120
RAW_OUTPUT_FILE = "whatsapp_messages_raw.json" # Output from scraping
FILTERED_OUTPUT_FILE_SUFFIX = "_filtered"      # Suffix for the filtered file
USE_SAVED_SESSION = True
USER_DATA_DIR = "whatsapp_session"

# --- Locators (Check/Update these if script fails) ---
QR_CODE_SELECTOR = '[data-testid="qrcode"]'
LOGGED_IN_INDICATOR = '#pane-side'
SEARCH_BOX_XPATH = '//div[@contenteditable="true"][@data-tab="3"]'
CHAT_LINK_XPATH_TEMPLATE = f'//span[@title="{CHAT_NAME}"]'
MESSAGE_PANE_XPATH = '//div[@data-testid="conversation-panel-messages"]'
MESSAGE_CONTAINER_XPATH = './/div[contains(@class, "message-")]'
SENDER_NAME_XPATH = './/span[contains(@class, "sender-name")] | .//div[contains(@class, "_11JPr")]/span[@dir="auto"]'
MESSAGE_TEXT_XPATH = './/span[contains(@class, "selectable-text")]/span'
TIMESTAMP_XPATH = './/span[@data-testid="message-meta"]//span'

# --- Selenium Scraping Functions (mostly unchanged from previous version) ---

def setup_driver():
    """Sets up the Selenium WebDriver."""
    options = ChromeOptions()
    if USE_SAVED_SESSION:
        if not os.path.exists(USER_DATA_DIR):
            os.makedirs(USER_DATA_DIR)
        options.add_argument(f"user-data-dir={os.path.abspath(USER_DATA_DIR)}")
        print(f"Attempting to use session data from: {os.path.abspath(USER_DATA_DIR)}")
    options.add_argument("--disable-extensions")
    # options.add_argument("--incognito") # Don't use incognito if saving session
    options.add_argument("--start-maximized")
    # options.add_experimental_option("detach", True) # Keep open after script finishes

    try:
        service = ChromeService(executable_path=ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("WebDriver setup successful.")
        return driver
    except Exception as e:
        print(f"Error setting up WebDriver: {e}")
        return None

def wait_for_login(driver):
    """Waits for the user to log in."""
    print("Opening WhatsApp Web...")
    driver.get("https://web.whatsapp.com")
    try:
        print("Checking for existing session...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, LOGGED_IN_INDICATOR))
        )
        print("Logged in using saved session.")
        return True
    except TimeoutException:
        print("Existing session not found or expired.")
        print(f"Please scan the QR code within {LOGIN_TIMEOUT} seconds...")
        try:
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, QR_CODE_SELECTOR))
            )
            print("QR Code detected. Waiting for scan...")
            WebDriverWait(driver, LOGIN_TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, LOGGED_IN_INDICATOR))
            )
            print("Login successful!")
            return True
        except TimeoutException:
            print("Login timeout. Did not detect successful login.")
            return False
        except Exception as e:
            print(f"An error occurred during login wait: {e}")
            return False

def find_and_open_chat(driver):
    """Searches for and clicks on the specified chat."""
    print(f"Searching for chat: '{CHAT_NAME}'...")
    try:
        wait = WebDriverWait(driver, WAIT_TIMEOUT)
        search_box = wait.until(EC.presence_of_element_located((By.XPATH, SEARCH_BOX_XPATH)))
        search_box.clear()
        search_box.click()
        search_box.send_keys(CHAT_NAME)
        time.sleep(2)
        chat_link_xpath = CHAT_LINK_XPATH_TEMPLATE
        chat_link = wait.until(EC.element_to_be_clickable((By.XPATH, chat_link_xpath)))
        chat_link.click()
        print(f"Clicked on chat: '{CHAT_NAME}'")
        wait.until(EC.presence_of_element_located((By.XPATH, MESSAGE_PANE_XPATH)))
        print("Chat opened successfully.")
        return True
    except TimeoutException:
        print(f"Error: Could not find or open chat '{CHAT_NAME}' within timeout.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while opening chat: {e}")
        return False

def scroll_up_to_ (remove potential unicode chars sometimes seen in exports)
    # Although less likely needed with direct scraping, good practice.
    normalized_sender = sender_name.replace('\u200e', '').strip()

    action_phrases = [
        "joined", "left", "added", "removed", "created this group",
        "created group", "changed the subject", "changed this group's icon",
        "changed their phone number to a new number.",
        "joined using this community's invite link", "was added", "was removed",
        "You joined", "You were added", "You created this group",
        "You're now an admin", "You're no longer an admin",
        "Tap to learn more.", "This group was created", # Phrases often without explicit sender
    ]

    # Check 1: Common system messages that might appear as text content
    # (Often without a 'Sender Name:' prefix in the web view)
    lower_content = message_content.lower()
    if any(phrase in lower_content for phrase in [
             "messages and calls are end-to-end encrypted",
             "no one outside of this chat",
             "security code with",
             "changed.", # Very generic, but often follows a name+action
             "created this community",
             "created the group",
             "you were added",
             "you joined",
             "tapped to join",
             "missed voice call",
             "missed videoload_messages(driver):
    """Scrolls up in the message pane."""
    print(f"Scrolling up {SCROLL_COUNT} times...")
    try:
        message_pane = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.XPATH, MESSAGE_PANE_XPATH))
        )
        scrollable_element = driver.execute_script(
             "return arguments[0].closest('[class*=\"copyable-area\"]')", message_pane
        )
        if scrollable_element is None:
             scrollable_element = driver.execute_script("return arguments[0].parentNode;", message_pane)
             if scrollable_element is None:
                  print("Could not reliably identify scrollable element. Using message pane.")
                  scrollable_element = message_pane

        last_scroll_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_element)
        no_change_count = 0

        for i in range(SCROLL_COUNT):
            driver.execute_script("arguments[0].scrollTop = 0;", scrollable_element)
            print(f"Scroll attempt {i+1}/{SCROLL_COUNT}")
            time.sleep(SCROLL_PAUSE_TIME)
            current_scroll_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_element)
            if current_scroll_height == last_scroll_height:
                 no_change_count += 1
            else:
                 no_change_count = 0
            last_scroll_height = current_scroll_height
            if no_change_count >= 3:
                 print("Stopping scroll early (no new content loaded).")
                 break
        print("Scrolling finished.")
    except TimeoutException:
        print("Error: Could not find the message pane for scrolling.")
    except Exception as e:
        print(f"An error occurred during scrolling: {e}")

def scrape_messages(driver):
    """Finds message elements and extracts call",
    ]):
        # Check if it's *just* the encryption message or similar short system info
        if len(message_content) < 100 and ("encrypted" in lower_content or "security code" in lower_content):
             return True
        # Check common join/left/create messages which might not have a sender scraped
        if sender data."""
    print("Starting message scraping...")
    messages_data = []
    processed_message_ids = set()
    try:
        time.sleep(2) # Wait for render
        message_pane = driver.find_element(By.XPATH, MESSAGE_PANE_XPATH)
        message_elements = message_pane.find_elements(By.XPATH, MESSAGE_CONTAINER_XPATH)
        print(f"Found {len(message_elements)} potential message elements.")

        if not message_elements:
            print(f"Warning: No message elements found with X_name == "Me/System" or not sender_name: # Check if scraper assigned default or found none
            if any (PATH: {MESSAGE_CONTAINER_XPATH}")
            return []

        for element in message_elements:
            try:
                element_id = element.get_attribute('data-id') or element.id
                if elementphrase in lower_content for phrase in action_phrases):
                 return True


    # Check 2: Pattern_id in processed_message_ids: continue
                processed_message_ids.add(element_id)

                sender = "Me/System" # Default
                text = "[Non-text content or empty]" # Default
                timestamp = None

                try:
                    sender_element = element.find_element(By.XPATH, SENDER_NAME_XPATH)
                     where sender name might be embedded in the message text
    # (Less common with scraping compared to export files, but worthsender = sender_element.text.strip()
                except NoSuchElementException: pass # Keep default
                except St checking)
    # Example: "\u200eJohn Doe added Jane Doe" where sender is "MealeElementReferenceException: continue

                try:
                    text_element = element.find_element(By.XPATH, MESSAGE_TEXT_XPATH)
                    text = text_element.text.strip()
                except NoSuchElementException:
                     try: # Check for images
                        img_element = element.find_element(By.TAG_NAME, "img")
                        alt/System" but text contains names
    # This is harder to replicate perfectly without the export file structure.
    # We_text = img_element.get_attribute('alt')
                        text = f"[Image: {alt_text}]" if alt_text else "[Image/Media]"
                     except NoSuchElementException: pass # Keep default
                except StaleElementReferenceException: continue

                try:
                    timestamp_element = element.find_element(By.XPATH, focus on the `message_content` containing action phrases, potentially with names.
    if sender_name == "Me/System" or not sender TIMESTAMP_XPATH)
                    timestamp = timestamp_element.text.strip()
                except NoSuchElementException: pass #_name: # If no specific sender was found by scraper
        temp_content = message_content.replace('\u200e', ''). Keep default (None)
                except StaleElementReferenceException: continue

                # Add if text is meaningful (not the default empty/non-text placeholder)
                if text and text != "[Non-text content or empty]":
                    messagestrip()
        # Look for "<Name> <action_phrase>" pattern
        for phrase in action_ph_info = {
                        "sender": sender,
                        "text": text,
                        "timestamp": timestamp,
                    }
                    messages_data.append(message_info)

            except StaleElementReferenceException:rases:
            if phrase in temp_content:
                # Simple check: if the phrase exists in a message with
                 print("Skipping stale message element.")
                 continue
            except Exception as e:
                print(f"Error processing one message element: {e}")

        print(f"Successfully scraped {len(messages_data)} messages.")
 no clear sender,
                # it's likely automated. Might need refinement for edge cases.
                # Example: "John        return messages_data

    except NoSuchElementException:
        print(f"Error: Could not find message pane or containers. Check XPATHs.")
        return []
    except Exception as e:
        print(f"An unexpected error occurred during scraping: {e}")
        return []

def save_to_json(data, filename):
    """Saves data Doe changed the subject to..."
                # We check if the part *after* a potential name matches an action phrase.
                words = temp to a JSON file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:_content.split()
                if len(words) > 1:
                    action_part = " ".join(words[1:]) #
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Data successfully saved to {filename}")
        return True
    except IOError as e:
        print( Check starting from second word
                    if any(action_part.startswith(p) for p in action_phrasesf"Error saving data to JSON file {filename}: {e}")
        return False
    except Exception as e):
                        return True
                    action_part = " ".join(words[2:]) # Check starting from third word (:
        print(f"An unexpected error occurred saving JSON to {filename}: {e}")
        return False


# --- Filtering Logic (Adapted for JSON structure) ---

def is_automated_message(sender_name, message_content):
e.g., "\u200e Name Action")
                    if any(action_part.startswith(p) for p in action_    """Checks if a message is an automated system message based on sender/content."""
    # Note: This check is less reliable than the original regex on exported .txt
    # as the structure might differ slightly in scraped data.

phrases):
                        return True

    # Check 3: Based on scraped sender name directly (if available)
    # This is less common for automated messages, but sometimes sender is assigned weirdly
    # Example: Sender = "You" for messages like "You created the    # Handle the "Me/System" placeholder from scraping
    effective_sender = sender_name if sender_name != " group"
    if normalized_sender.lower() == "you":
        if any(phrase in lower_content for phrase in actionMe/System" else None

    action_phrases = [
        "joined", "left", "added_phrases):
             return True


    # If none of the above matched, assume it's a user message
    return False


def", "removed", "created this group",
        "created group", "changed the subject", "changed this group's icon filter_scraped_messages(messages_list):
    """
    Filters the list of scraped message dictionaries.",
        "changed their phone number to a new number.",
        "joined using this community's invite link", "was added", "was removed",
        "Your security code with",
        "Messages and calls are end-
    Removes messages identified as automated/system messages.
    Does NOT filter by date due to limitations in scraped timestamp format.
    """
to-end encrypted.",
        "You created group", # Variations for self-actions
        "You changed the subject    if not messages_list:
        return []

    filtered_list = []
    removed_count = 0
    for",
        "You changed this group's icon",
        "You added",
        "You removed", message in messages_list:
        sender = message.get("sender")
        text = message.get("text")

        # Use
    ]

    # Check 1: Does the message *start* with an action phrase (often system messages)?
    if any(message_content.strip().startswith(phrase) for phrase in action_phrases):
        return True

 .get() for safer access, provide defaults if None
        if not is_automated_message(sender, text):
            filtered_list.    # Check 2: If we have an effective sender, check for the "Sender action" pattern
    # Theappend(message)
        else:
            removed_count += 1
            # Debug print (optional)
            # print(f '\u200e' might not be present in scraped data, so we check more simply.
    if effective_sender:"Filtered out: Sender='{sender}', Text='{text[:60]}...'")

    print(f"Filtering complete. Removed {removed_count} automated/system messages.")
    return filtered_list


# --- Selenium Functions
        # Pattern: "Sender removed User", "Sender added User" etc.
        if any(f"{effective (Mostly unchanged, except for minor debug/logging) ---

def setup_driver():
    """Sets up the Selenium WebDriver."""_sender} {phrase}" in message_content for phrase in action_phrases):
             return True

    # Check 3: Specific
    options = ChromeOptions()
    # options = EdgeOptions() # Uncomment for Edge

    if USE_SAVED_SESSION common system messages
    if "Messages and calls are end-to-end encrypted." in message_content:
:
        if not os.path.exists(USER_DATA_DIR):
            os.makedirs(USER        return True
    if "security code" in message_content and ("changed" in message_content or "_DATA_DIR)
        # Use absolute path for consistency
        abs_user_data_dir = os.path.abspath(USERwith" in message_content):
        return True
    if message_content.endswith("changed to"): # Phone_DATA_DIR)
        options.add_argument(f"user-data-dir={abs_user_data_dir}") number change notification often ends like this
         return True

    # Add more specific rules here if needed based on observed automated
        print(f"Attempting to use session data from: {abs_user_data_dir}")
    else:
          messages

    return False


def filter_scraped_json_data(input_data):
    """
options.add_argument("--incognito") # Use incognito if not saving session

    # Standard options
    options.add_argument("--disable-extensions")
    # options.add_argument("--headless") # Run headless (no browser window) -    Filters a list of message dictionaries (from scraped JSON).
    Removes automated messages. Date filtering is NOT performed might affect login/QR
    options.add_argument("--start-maximized")
    options.add_.
    Returns the filtered list and the count of messages kept.
    """
    if not isinstance(input_data, list):
        raise TypeError("Input data must be a list of dictionaries.")

    filtered_messages = []
    argument('--log-level=3') # Suppress excessive console logs from Chrome/Driver
    options.add_experimental_messages_processed_count = 0
    messages_kept_count = 0

    for msg in input_data:
        option('excludeSwitches', ['enable-logging']) # Suppress DevTools logs

    try:
        # Usingmessages_processed_count += 1
        sender = msg.get("sender", "Me/System") # webdriver-manager
        service = ChromeService(executable_path=ChromeDriverManager().install())
        # service = EdgeService Use default if missing
        text = msg.get("text", "")          # Use empty string if missing

        if not is_(executable_path=EdgeChromiumDriverManager().install()) # For Edge
        driver = webdriver.Chrome(serviceautomated_message(sender, text):
            filtered_messages.append(msg)
            messages_kept_count += =service, options=options)
        # driver = webdriver.Edge(service=service, options=options) # For Edge
        1
        # else: print(f"Filtered automated: Sender='{sender}', Text='{text[:50]}...'print("WebDriver setup successful.")
        return driver
    except Exception as e:
        print(f"Error setting up WebDriver: {e}")
        print("Please ensure you have Google Chrome (or MS Edge) installed.")") # Debugging

    return filtered_messages, messages_processed_count, messages_kept_count


# --- GUI Interaction
        print("If using manual webdriver, ensure it's in your PATH or path is correct.")
        return None

def for Filtering ---

def run_filter_process_gui():
    """Launches a GUI to select a JSON file and filter wait_for_login(driver):
    """Waits for the user to log in (QR scan or session load)."""
    print("Opening WhatsApp Web...")
    driver.get("https://web.whatsapp.com")

    try:
 it."""
    root = tk.Tk()
    root.withdraw() # Hide the main tkinter window

    # Ask        print("Checking for existing session...")
        # Wait briefly to see if we are logged in immediately from session data user to select the *input JSON* file
    input_filepath = filedialog.askopenfilename(
        title
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, LOGGED_IN_INDICATOR))
        )
        print("Logged in using saved session.")
        return True
    except TimeoutException:
        print("Existing session not found or expired.")
        # Check if QR="Select Scraped WhatsApp JSON File to Filter",
        filetypes=[("JSON files", "*.json"), ("All code is displayed
        try:
             WebDriverWait(driver, WAIT_TIMEOUT).until(
                 EC.presence_ files", "*.*")]
    )

    if not input_filepath:
        messagebox.showinfo("Cancelled", "No fileof_element_located((By.CSS_SELECTOR, QR_CODE_SELECTOR))
             )
             print selected. Filtering cancelled.")
        return

    # --- Generate Output Filename ---
    try:
        input(f"QR Code detected. Please scan within {LOGIN_TIMEOUT} seconds...")
             # Now wait for the login to complete (chat_dir = os.path.dirname(input_filepath)
        base_name = os.path.basename(input_filepath)
        name_part, ext_part = os.path.splitext(base_name)

        # Ensure pane appears)
             WebDriverWait(driver, LOGIN_TIMEOUT).until(
                 EC.presence_of_element_located((By.CSS_SELECTOR, LOGGED_IN_INDICATOR))
             )
             print("Login successful!")
             # extension is .json
        if ext_part.lower() != ".json":
             ext_part = ".json" # Force .json extension

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
         Add a small delay for page elements to stabilize after login
             time.sleep(5)
             return True
        # Add suffix before the extension
        output_filename = f"{name_part}{FILTERED_OUTPUT_FILE_SUFFIX}_{except TimeoutException:
             # Handle cases where QR code doesn't appear (e.g., already logged in buttimestamp}{ext_part}"
        output_filepath = os.path.join(input_dir, output_filename)

    except Exception as e:
        messagebox.showerror("Error", f"Could not determine output file path: {e}") indicator check failed, or other error)
             # Or cases where login takes too long after QR scan
             print
        return

    # --- Run the Filtering ---
    try:
        print(f"Filtering input JSON("Login timeout or QR code not found/scanned in time.")
             # Check again if maybe login succeeded just: {input_filepath}")
        print(f"Filtered output JSON: {output_filepath}")

        # 1. Read the input JSON
        with open(input_filepath, 'r', encoding='utf-8') as f:
            sc as timeout hit
             try:
                  driver.find_element(By.CSS_SELECTOR, LOGGED_IN_INDICATOR)
raped_data = json.load(f)

        # 2. Filter the data (no date filtering possible here)
        filtered_data, processed_count, kept_count = filter_scraped_json_data(scraped_data                  print("Login seems to have succeeded just after timeout check.")
                  time.sleep(5)
                  return True
             except)

        # 3. Save the filtered data
        if save_to_json(filtered_data, output_filepath):
            if NoSuchElementException:
                  print("Could not confirm login.")
                  return False
        except Exception as e:
            print( kept_count > 0:
                messagebox.showinfo("Success",
                                    f"JSON data filtered successfully!\n"f"An error occurred during login wait: {e}")
            return False

def find_and_open_
                                    f"(Automated system messages removed. Date filtering was not applied.)\n\n"
                                    chat(driver):
    """Searches for and clicks on the specified chat."""
    print(f"Searching for chat: '{f"Processed {processed_count} messages.\n"
                                    f"Kept {kept_count}CHAT_NAME}'...")
    try:
        wait = WebDriverWait(driver, WAIT_TIMEOUT)

        #  messages.\n\n"
                                    f"Saved to:\n{output_filepath}")
            else:1. Find the search box more reliably
        # Adjusted XPath to be potentially more robust
        search_xpath = '//
                 messagebox.showwarning("Completed",
                                       f"Filtering complete, but no messages remained after removingdiv[contains(@class, "lexical-rich-text-input")]//p[@class="selectable-text copy automated ones.\n\n"
                                       f"Processed {processed_count} messages.\n"
                                       f"An empty list was saved to:\n{output_filepath}")
        else:
            # save_to_json wouldable-text"][@contenteditable="true"]'
        try:
            search_box = wait.until(
                EC have printed an error, show dialog too
             messagebox.showerror("Error", f"Failed to save filtered data to:\.presence_of_element_located((By.XPATH, search_xpath))
            )
        except TimeoutException:
            #n{output_filepath}\n\nCheck console output for details.")


    except FileNotFoundError:
        messagebox.showerror("Error", Fallback to original XPath if new one fails
            print("Using fallback search box XPath.")
            search_box = wait f"Input JSON file not found:\n{input_filepath}")
    except json.JSONDecodeError:
.until(
                EC.presence_of_element_located((By.XPATH, SEARCH_BOX_XPATH         messagebox.showerror("Error", f"Invalid JSON format in file:\n{input_filepath}")
    except ())
        )

        # Click might be needed if it's not focused
        try:
            search_box.clickIOError, TypeError, RuntimeError) as e:
        print(f"Error during filtering: {e}")
        messagebox.showerror("Error", f"An error occurred during filtering:\n\n{e}")
    except Exception as e:
        print()
        except Exception as click_err:
            print(f"Note: Clicking search box generated an event(f"Unexpected Error during filtering: {e}")
        messagebox.showerror("Unexpected Error", f"An unexpected error occurred:\n error (often ignorable): {click_err}")

        search_box.clear()
        search_box.send_keys\n{e}")


# --- Main Execution ---
if __name__ == "__main__":
    driver = None
    raw_data_saved = False
    try:
        # --- Part 1: Scraping ---
        driver(CHAT_NAME)
        print(f"Typed '{CHAT_NAME}' into search.")
        time.sleep(3) # Allow search results to populate and render

        # 2. Find the chat link in the results
        chat_link_ = setup_driver()
        if driver:
            if wait_for_login(driver):
                if find_and_open_chat(driver):
                    scroll_up_to_load_messages(driver)
                    scraped_data = scrape_messages(driver)xpath = CHAT_LINK_XPATH_TEMPLATE
        # Use visibility_of_element_located for better interaction

                    if scraped_data:
                        # Save the raw scraped data
                        if save_to_json( readiness
        chat_link = wait.until(
             EC.visibility_of_element_located((Byscraped_data, RAW_OUTPUT_FILE):
                             raw_data_saved = True
                        else:
                             print(.XPATH, chat_link_xpath))
        )
        print("Chat found in search results.")

        # 3. Click the chatf"Warning: Failed to save raw data to {RAW_OUTPUT_FILE}")
                    else:
                        print("No messages were scraped. No raw data file created.")
                else:
                    print("Could not open the target chat. Exiting scraping.")
            else:
                 link - JS click can sometimes be more reliable
        driver.execute_script("arguments[0].click();", chat_link)print("Login failed or timed out. Exiting scraping.")
        else:
            print("WebDriver setup failed. Exiting scraping
        # chat_link.click() # Standard click as fallback
        print(f"Clicked on chat: '{CHAT_NAME}'.")

    except Exception as e:
        print(f"\n--- An unexpected error occurred during scraping ---")
        print(f"")

        # 4. Wait for the message pane of the chat to be identifiable
        wait.until(
            Error Type: {type(e).__name__}")
        print(f"Error Details: {e}")
EC.presence_of_element_located((By.XPATH, MESSAGE_PANE_XPATH))
        )        import traceback
        traceback.print_exc() # Print full traceback for scraping errors

    finally:
        if driver:
            print("Closing WebDriver...")
            driver.quit()
            print("WebDriver closed.")

    # --- Part 2: Optional
        # Add a small delay for chat content to start loading
        time.sleep(3)
        print("Chat opened Filtering via GUI ---
    if raw_data_saved:
         # Ask user if they want to filter the successfully.")
        return True

    except TimeoutException:
        print(f"Error: Could not find or open chat file just created
         root = tk.Tk()
         root.withdraw() # Hide root window
         # '{CHAT_NAME}' within timeout.")
        print("Possible reasons:")
        print(" - CHAT_NAME is not exact (case-sensitive).")
        print(" - Chat is not pinned or visible in the initial list, requiring scrolling.")
        print(" - Use tk simpledialog or messagebox for simple yes/no if preferred,
         # but let's just launch the filter process WhatsApp Web interface has changed, breaking XPATH selectors.")
        print(f"   - Search Box XPATH used: {search_xpath} (or fallback {SEARCH_BOX_XPATH})")
        print(f"    directly for simplicity.
         # User can choose the file they want (including the one just saved).
         print("\n--- Scrap- Chat Link XPATH used: {CHAT_LINK_XPATH_TEMPLATE}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while opening chat: {e}")
        return False

def scroll_up_toing finished ---")
         print(f"Raw data saved to: {RAW_OUTPUT_FILE}")
         print_load_messages(driver):
    """Scrolls up in the message pane to load older messages."""
    print(("Launching filter tool...")
         run_filter_process_gui()

    elif os.path.exists(RAW_OUTPUTf"Scrolling up {SCROLL_COUNT} times to load messages...")
    try:
        # Locate the specific_FILE):
         # Handle case where scraping failed but a previous raw file exists
         print("\n--- Scraping did scrollable element - this is often the parent of the message pane
        # WhatsApp uses dynamic class names, so finding not complete successfully ---")
         print(f"An existing raw data file was found: {RAW_OUTPUT_FILE a stable parent can be tricky.
        # This XPath tries to find the main scrollable area for chats.
        scrollable_xpath}")
         print("You can still launch the filter tool manually if needed,")
         print("or run the script again = '//div[contains(@class, "copyable-area")]/div[contains(@class, "scrollable")] to attempt scraping.")
         # Optionally, launch the GUI anyway:
         # print("Launching filter tool...")
         # run_filter_process_gui()
    else:
         print("\n--- Scraping did not complete successfully and no raw data file was found. ---")

    print("\nScript finished.")
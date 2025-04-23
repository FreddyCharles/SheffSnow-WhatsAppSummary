# --- START OF FILE scrapingProgram.py (Edge Version) ---

import time
import json
import os
import re
from datetime import datetime # Keep for timestamp in output filename
import tkinter as tk
from tkinter import filedialog, messagebox
import sys # For basic OS checks if needed, less critical for Edge
import traceback # For detailed error printing

from selenium import webdriver
# --- Edge Imports ---
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
# --- Edge WebDriver Manager ---
from webdriver_manager.microsoft import EdgeChromiumDriverManager
# --- Common Selenium imports ---
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, StaleElementReferenceException,
    SessionNotCreatedException # More specific exception
)


# --- Configuration ---
CHAT_NAME = "SheffSnow 2024/25 🏂🎿"  # <<< --- CHANGE THIS TO THE EXACT CHAT NAME
SCROLL_COUNT = 15                      # Number of times to scroll up (adjust as needed)
SCROLL_PAUSE_TIME = 1.5                # Seconds to wait between scrolls
WAIT_TIMEOUT = 60                      # Max seconds to wait for elements
LOGIN_TIMEOUT = 120                    # Max seconds to wait for QR scan / login
RAW_OUTPUT_FILE = "whatsapp_messages_raw.json" # Output from scraping
FILTERED_OUTPUT_FILE_SUFFIX = "_filtered"      # Suffix for the filtered file
USE_SAVED_SESSION = True               # Try reusing a session?
USER_DATA_DIR = "whatsapp_edge_session" # Directory for Edge session data

# --- Locators (Should be the same for Edge as for Chrome/Opera) ---
QR_CODE_SELECTOR = '[data-testid="qrcode"]'
LOGGED_IN_INDICATOR = '#pane-side'
SEARCH_XPATH_PRIMARY = '//div[contains(@class, "lexical-rich-text-input")]//p[@class="selectable-text copyable-text"][@contenteditable="true"]'
SEARCH_XPATH_FALLBACK = '//div[@contenteditable="true"][@data-tab="3"]'
CHAT_LINK_XPATH_TEMPLATE = f'//span[@title="{CHAT_NAME}"]'
MESSAGE_PANE_XPATH = '//div[@data-testid="conversation-panel-messages"]'
MESSAGE_CONTAINER_XPATH = './/div[contains(@class, "message-")]'
SENDER_NAME_XPATH = './/span[contains(@class, "sender-name")] | .//div[contains(@class, "_11JPr")]/span[@dir="auto"]'
MESSAGE_TEXT_XPATH = './/span[contains(@class, "selectable-text")]/span'
TIMESTAMP_XPATH = './/span[@data-testid="message-meta"]//span'

# --- Selenium Scraping Functions ---

def setup_driver():
    """Sets up the Selenium WebDriver for Microsoft Edge."""
    options = EdgeOptions()

    # --- Session Data for Edge ---
    if USE_SAVED_SESSION:
        if not os.path.exists(USER_DATA_DIR):
            try:
                os.makedirs(USER_DATA_DIR)
                print(f"Created session directory: {USER_DATA_DIR}")
            except OSError as e:
                 print(f"Error creating session directory {USER_DATA_DIR}: {e}")
                 # Decide: stop or continue without session? Stopping is safer.
                 print("Cannot proceed without session directory.")
                 return None
        # Always use absolute path for user data dir
        abs_user_data_dir = os.path.abspath(USER_DATA_DIR)
        # The argument format is slightly different for Edge options
        options.add_argument(f"--user-data-dir={abs_user_data_dir}")
        print(f"Attempting to use Edge session data from: {abs_user_data_dir}")
    # else: # Optional: Use InPrivate if not saving session
    #     options.add_argument("-inprivate")

    # --- Standard Options for Edge ---
    # Suppress excessive logging
    options.add_argument('--log-level=3')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    # Run maximized
    options.add_argument("--start-maximized")
    # Disable extensions (good practice for stability)
    options.add_argument("--disable-extensions")
    # Headless mode (optional, may affect WhatsApp Web login)
    # options.add_argument("--headless")
    # options.add_argument("--disable-gpu") # Often needed with headless

    # Keep browser open after script finishes (for debugging)
    # options.add_experimental_option("detach", True)

    try:
        # --- Use EdgeChromiumDriverManager to get the correct msedgedriver ---
        print("Installing/Updating msedgedriver...")
        # Explicitly provide path for service initialization
        driver_path = EdgeChromiumDriverManager().install()
        service = EdgeService(executable_path=driver_path)
        print(f"Using msedgedriver executable at: {driver_path}")

        # --- Instantiate webdriver.Edge ---
        print("Initializing Edge WebDriver...")
        driver = webdriver.Edge(service=service, options=options)

        print("Edge WebDriver setup successful.")
        return driver

    except SessionNotCreatedException as e:
        print(f"\n--- Error: Failed to create Edge session ---")
        print(f"Message: {e.msg}")
        print("-" * 30)
        print("Possible causes:")
        print("1. Incompatible msedgedriver version with installed Edge browser.")
        print("   - Try updating Edge browser (`edge://settings/help`).")
        print("   - `webdriver-manager` usually handles this, but manual download might be needed in rare cases.")
        print("2. Edge browser installation issue or corrupted profile.")
        print(f"3. Issue with the user data directory: {USER_DATA_DIR}")
        print("   - Try deleting this folder and running again (will require new login).")
        print("4. Antivirus/Firewall interference.")
        print("-" * 30)
        # traceback.print_exc() # Uncomment for full stack trace if needed
        return None
    except Exception as e:
        print(f"\n--- An unexpected error occurred setting up Edge WebDriver ---")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Details: {e}")
        print("-" * 30)
        traceback.print_exc()
        return None


# --- Other Functions (wait_for_login, find_and_open_chat, scroll_up_to_load_messages, scrape_messages, save_to_json, is_automated_message, filter_scraped_json_data, run_filter_process_gui) ---
# These functions use standard Selenium interactions and should work with Edge without modification.
# Make sure you have the complete definitions of these functions from the previous versions pasted below.

# --- wait_for_login Function ---
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
        time.sleep(3) # Allow UI to settle
        return True
    except TimeoutException:
        print("Existing session not found or expired.")
        try:
             # Wait for QR code OR already logged in indicator (race condition possible)
             element_found = WebDriverWait(driver, WAIT_TIMEOUT).until(
                 EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, QR_CODE_SELECTOR)),
                    EC.presence_of_element_located((By.CSS_SELECTOR, LOGGED_IN_INDICATOR))
                 )
             )
             # Check which element appeared
             try:
                 is_qr_code = False
                 try:
                     # Check attribute that reliably identifies the QR code element
                     if element_found.get_attribute("data-testid") == "qrcode":
                         is_qr_code = True
                 except Exception: pass # Handle potential staleness

                 if is_qr_code:
                     print(f"QR Code detected. Please scan within {LOGIN_TIMEOUT} seconds...")
                     # Now wait specifically for the login to complete
                     WebDriverWait(driver, LOGIN_TIMEOUT).until(
                         EC.presence_of_element_located((By.CSS_SELECTOR, LOGGED_IN_INDICATOR))
                     )
                     print("Login successful after QR scan!")
                     time.sleep(5) # Allow UI to settle
                     return True
                 else:
                     # If it wasn't the QR code, it must be the logged-in indicator
                     print("Login detected without QR code prompt (fast session load or QR check issue).")
                     time.sleep(3)
                     # Verify login state again
                     try:
                         driver.find_element(By.CSS_SELECTOR, LOGGED_IN_INDICATOR)
                         return True
                     except NoSuchElementException:
                         print("Error: Detected logged-in indicator initially, but it disappeared.")
                         return False

             except TimeoutException:
                  print("Login timeout after QR code was displayed.")
                  try:
                       driver.find_element(By.CSS_SELECTOR, LOGGED_IN_INDICATOR)
                       print("Login seems to have succeeded just after timeout check.")
                       time.sleep(3)
                       return True
                  except NoSuchElementException:
                       print("Could not confirm login after QR timeout.")
                       return False
             except Exception as e_inner:
                print(f"An unexpected error occurred checking login state: {e_inner}")
                return False

        except TimeoutException:
             print(f"Login timeout: Neither QR code nor main chat interface appeared within {WAIT_TIMEOUT}s.")
             return False
        except Exception as e:
            print(f"An error occurred during login wait: {e}")
            traceback.print_exc()
            return False

# --- find_and_open_chat Function ---
def find_and_open_chat(driver):
    """Searches for and clicks on the specified chat."""
    print(f"Searching for chat: '{CHAT_NAME}'...")
    try:
        wait = WebDriverWait(driver, WAIT_TIMEOUT)

        # 1. Find the search box
        try:
            print("Waiting for search box (primary XPath)...")
            search_box = wait.until(
                EC.presence_of_element_located((By.XPATH, SEARCH_XPATH_PRIMARY))
            )
            print("Using primary search box XPath.")
        except TimeoutException:
            try:
                print("Primary search box XPath failed, waiting for fallback...")
                search_box = wait.until(
                    EC.presence_of_element_located((By.XPATH, SEARCH_XPATH_FALLBACK))
                )
                print("Using fallback search box XPath.")
            except TimeoutException:
                 print("Error: Could not find search box using either XPath.")
                 print(f"   Primary: {SEARCH_XPATH_PRIMARY}")
                 print(f"   Fallback: {SEARCH_XPATH_FALLBACK}")
                 # Optional: Save page source for debugging
                 # with open("debug_page_source_search.html", "w", encoding="utf-8") as f:
                 #      f.write(driver.page_source)
                 # print("Saved page source to debug_page_source_search.html")
                 return False

        # 2. Interact with the search box
        try:
            print("Clicking search box...")
            wait.until(EC.element_to_be_clickable(search_box))
            search_box.click()
            time.sleep(0.5)
            print("Clearing search box...")
            search_box.clear()
            time.sleep(0.5)
            print(f"Typing '{CHAT_NAME}' into search box...")
            search_box.send_keys(CHAT_NAME)
            print("Waiting for search results...")
            time.sleep(3)
        except StaleElementReferenceException:
            print("Error: Search box became stale during interaction. Retrying find...")
            try:
                 # Re-find using the method that worked initially or primary
                 search_box = wait.until(EC.presence_of_element_located((By.XPATH, SEARCH_XPATH_PRIMARY)))
                 search_box.click()
                 search_box.clear()
                 search_box.send_keys(CHAT_NAME)
                 time.sleep(3)
            except Exception as retry_err:
                 print(f"Retry interacting with search box failed: {retry_err}")
                 return False
        except Exception as interact_err:
            print(f"Error interacting with search box: {interact_err}")
            traceback.print_exc()
            return False

        # 3. Find the chat link in the results
        chat_link_xpath = CHAT_LINK_XPATH_TEMPLATE
        try:
            print(f"Waiting for chat link: '{chat_link_xpath}'")
            # Use visibility first, then check clickability
            chat_link = wait.until(EC.visibility_of_element_located((By.XPATH, chat_link_xpath)))
            chat_link = wait.until(EC.element_to_be_clickable(chat_link)) # Ensure it's ready
            print("Chat found in search results.")
        except TimeoutException:
            print(f"Error: Could not find clickable chat '{CHAT_NAME}' in results within timeout.")
            print(f"   XPath used: {chat_link_xpath}")
            print("   Is CHAT_NAME exact? Are results visible?")
            # Optional: Save page source
            # with open("debug_page_source_chatlink.html", "w", encoding="utf-8") as f:
            #     f.write(driver.page_source)
            # print("Saved page source to debug_page_source_chatlink.html")
            return False

        # 4. Click the chat link
        try:
            print("Attempting to click chat link...")
            chat_link.click()
            print(f"Clicked on chat: '{CHAT_NAME}'.")
        except StaleElementReferenceException:
            print("Error: Chat link became stale before clicking. Retrying find and click...")
            try:
                chat_link = wait.until(EC.element_to_be_clickable((By.XPATH, chat_link_xpath)))
                chat_link.click()
                print("Retry click successful.")
            except Exception as retry_click_err:
                print(f"Retry click failed: {retry_click_err}")
                return False
        except Exception as click_err:
            print(f"Error clicking chat link: {click_err}")
            print("   Element might be obscured. Trying JavaScript click...")
            try:
                driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", chat_link)
                print("JavaScript click successful.")
            except Exception as js_click_err:
                 print(f"JavaScript click also failed: {js_click_err}")
                 traceback.print_exc()
                 return False

        # 5. Wait for the message pane
        try:
            print("Waiting for chat message pane to load...")
            wait.until(
                EC.presence_of_element_located((By.XPATH, MESSAGE_PANE_XPATH))
            )
            time.sleep(3)
            print("Chat opened successfully.")
            return True
        except TimeoutException:
            print("Error: Message pane did not load after clicking chat.")
            print(f"   Message Pane XPath: {MESSAGE_PANE_XPATH}")
            return False

    except Exception as e:
        print(f"An unexpected error occurred while opening chat: {e}")
        traceback.print_exc()
        return False

# --- scroll_up_to_load_messages Function ---
def scroll_up_to_load_messages(driver):
    """Scrolls up in the message pane to load older messages."""
    print(f"Attempting to scroll up {SCROLL_COUNT} times to load messages...")
    try:
        wait = WebDriverWait(driver, WAIT_TIMEOUT)
        message_pane = wait.until(
            EC.presence_of_element_located((By.XPATH, MESSAGE_PANE_XPATH))
        )
        print("Message pane located.")

        scrollable_element = None
        try:
            print("Attempting to identify scrollable element via JavaScript...")
            # This JS script is generally reliable for finding the scrollable parent
            scrollable_element = driver.execute_script("""
                let el = arguments[0];
                for (let i = 0; i < 7 && el; i++) { // Increased search depth slightly
                    let style = window.getComputedStyle(el);
                    if (style.overflowY === 'scroll' || style.overflowY === 'auto') {
                        // Check if it seems like the main chat area (e.g., contains message list)
                         if (el.scrollHeight > el.clientHeight && el.clientHeight > 100 && (el.querySelector('[data-testid^="msg-container"]') || el.classList.contains('copyable-area'))) {
                             console.log('Found likely scrollable element:', el);
                             return el;
                         }
                    }
                    el = el.parentElement;
                }
                // Fallback if specific checks fail but overflow matches
                el = arguments[0].parentElement; // Start search again from parent
                 for (let i = 0; i < 5 && el; i++) {
                     let style = window.getComputedStyle(el);
                     if (style.overflowY === 'scroll' || style.overflowY === 'auto') {
                         if (el.scrollHeight > el.clientHeight && el.clientHeight > 100) {
                              console.log('Found potential scrollable element (fallback check):', el);
                              return el;
                         }
                     }
                     el = el.parentElement;
                 }
                console.log('JS check failed, falling back to message pane parent.');
                return arguments[0].parentElement; // Final fallback
                """, message_pane)
        except Exception as js_err:
             print(f"JavaScript error finding scrollable element: {js_err}. Falling back.")
             scrollable_element = None

        if not scrollable_element:
            print("Warning: Could not robustly detect scrollable element. Using message pane's parent.")
            try:
                 scrollable_element = driver.find_element(By.XPATH, f'{MESSAGE_PANE_XPATH}/..')
            except NoSuchElementException:
                 print("Error: Could not find message pane parent either. Cannot scroll.")
                 return

        print(f"Identified element for scrolling: Tag='{scrollable_element.tag_name}', Class='{scrollable_element.get_attribute('class') or 'N/A'}', ID='{scrollable_element.get_attribute('id') or 'N/A'}'")

        last_scroll_height = -1 # Initialize differently to ensure first check runs
        no_change_count = 0
        stable_count = 3 # Adjust stability threshold if needed

        print("Starting scroll loop...")
        for i in range(SCROLL_COUNT):
            try:
                # Scroll to top first
                driver.execute_script("arguments[0].scrollTop = 0;", scrollable_element)
                time.sleep(SCROLL_PAUSE_TIME) # Wait for content loading AFTER scrolling

                # Get height AFTER waiting
                current_scroll_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_element)

                # Check stability
                if current_scroll_height == last_scroll_height:
                     no_change_count += 1
                     print(f"  Scroll {i+1}/{SCROLL_COUNT}: Height {current_scroll_height} (unchanged - stable: {no_change_count}/{stable_count})")
                     if no_change_count >= stable_count:
                          print("Scroll height stabilized. Stopping scroll early.")
                          break
                else:
                     no_change_count = 0
                     print(f"  Scroll {i+1}/{SCROLL_COUNT}: Height {current_scroll_height} (was {last_scroll_height})")

                last_scroll_height = current_scroll_height

            except StaleElementReferenceException:
                 print(f"Warning: Scrollable element became stale during scroll {i+1}. Re-finding...")
                 try:
                     # Re-find using the most likely fallback
                     scrollable_element = driver.find_element(By.XPATH, f'{MESSAGE_PANE_XPATH}/..')
                     print("   Re-found scrollable element (using parent fallback).")
                     last_scroll_height = -1 # Reset checks
                     no_change_count = 0
                     # It might be better to retry the *same* iteration
                     # Decrement i? Or just continue to next? Continuing is simpler.
                     continue
                 except Exception as refind_err:
                     print(f"Error re-finding scrollable element: {refind_err}. Stopping scroll.")
                     break
            except Exception as scroll_loop_err:
                 print(f"Error during scroll loop iteration {i+1}: {scroll_loop_err}")
                 traceback.print_exc()
                 break # Stop on other errors

        print("Scrolling finished.")

    except TimeoutException:
        print("Error: Could not find the message pane before starting scroll.")
    except Exception as e:
        print(f"An unexpected error occurred during scrolling setup or execution: {e}")
        traceback.print_exc()

# --- scrape_messages Function ---
def scrape_messages(driver):
    """Finds message elements and extracts sender, text, and timestamp."""
    print("Starting message scraping...")
    messages_data = []
    processed_message_ids = set()
    try:
        time.sleep(2) # Wait for render after scroll
        message_pane = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, MESSAGE_PANE_XPATH))
        )
        print("Message pane found. Finding message elements...")

        # Find elements relative to the pane
        message_elements = message_pane.find_elements(By.XPATH, MESSAGE_CONTAINER_XPATH)
        print(f"Found {len(message_elements)} potential message container elements.")

        if not message_elements:
            print("Warning: No message elements found. Chat might be empty or selectors outdated.")
            return []

        count = 0
        for element in message_elements:
            count += 1
            try:
                # Try getting a more stable attribute if available, fallback to id
                element_unique_id = element.get_attribute('data-id') or element.id
            except StaleElementReferenceException:
                 print(f"Warn: Message element #{count} stale before getting ID. Skipping.")
                 continue

            if element_unique_id in processed_message_ids:
                # print(f"Debug: Skipping already processed element {element_unique_id}")
                continue

            try:
                sender = "Me/System"
                text = "[Error extracting text]" # Default changed
                timestamp = None

                # Extract Sender
                try:
                    sender_element = element.find_element(By.XPATH, SENDER_NAME_XPATH)
                    sender = sender_element.text.strip() if sender_element.text else "Me/System"
                except NoSuchElementException: pass # Expected for 'Me'/System
                except StaleElementReferenceException:
                    print(f"Warn: Stale sender element for msg {count} (ID {element_unique_id}).")

                # Extract Text
                try:
                    text_element = element.find_element(By.XPATH, MESSAGE_TEXT_XPATH)
                    # Get text content, including potential emojis (handled by text)
                    text = text_element.text.strip()
                    if not text: # If primary span is empty, check for media/other
                         try:
                            img_element = element.find_element(By.XPATH, './/img[@alt]')
                            alt_text = img_element.get_attribute('alt')
                            text = f"[Image: {alt_text.strip()}]" if alt_text else "[Image/Media]"
                         except NoSuchElementException:
                            try: # Check for deleted message indicator more reliably
                                deleted_div = element.find_element(By.XPATH, './/div[contains(@class,"message-deleted")]')
                                text = "[Message deleted]"
                            except NoSuchElementException:
                                try: # Check for stickers (often img without specific alt)
                                    sticker_img = element.find_element(By.XPATH, './/img[contains(@style, "sticker")]') # Heuristic check
                                    text = "[Sticker]"
                                except NoSuchElementException:
                                     # Add checks for polls, location, contacts etc. if needed
                                     text = "[Empty or unsupported content]"
                except NoSuchElementException: # If primary text span itself is missing
                     try: # Still check for media/deleted
                        img_element = element.find_element(By.XPATH, './/img[@alt]')
                        alt_text = img_element.get_attribute('alt')
                        text = f"[Image: {alt_text.strip()}]" if alt_text else "[Image/Media]"
                     except NoSuchElementException:
                         try:
                             deleted_div = element.find_element(By.XPATH, './/div[contains(@class,"message-deleted")]')
                             text = "[Message deleted]"
                         except NoSuchElementException:
                              text = "[Unknown content structure]"
                except StaleElementReferenceException:
                     print(f"Warn: Stale text element for msg {count} (ID {element_unique_id}). Skipping message.")
                     continue # Skip if text is lost

                # Extract Timestamp
                try:
                    # Ensure finding relative to the current message element
                    timestamp_element = element.find_element(By.XPATH, TIMESTAMP_XPATH)
                    timestamp = timestamp_element.text.strip()
                except NoSuchElementException: timestamp = None
                except StaleElementReferenceException:
                    print(f"Warn: Stale timestamp element for msg {count} (ID {element_unique_id}).")
                    timestamp = None

                # Append extracted data
                message_info = {
                    "sender": sender, "text": text, "timestamp": timestamp,
                }
                messages_data.append(message_info)
                processed_message_ids.add(element_unique_id)

            except StaleElementReferenceException:
                 print(f"Warn: Stale message container (Msg {count}, ID {element_unique_id}). Skipping.")
                 continue
            except Exception as e_inner:
                print(f"Error processing message element #{count} (ID {element_unique_id}): {type(e_inner).__name__} - {e_inner}")
                # Optional: Save HTML of problematic element
                # try:
                #     with open(f"debug_element_{element_unique_id}.html", "w", encoding="utf-8") as f_debug:
                #         f_debug.write(element.get_attribute('outerHTML'))
                # except: pass

        print(f"Successfully processed {len(messages_data)} messages.")
        return messages_data

    except TimeoutException:
        print("Error: Message pane not found before scraping messages.")
        return []
    except Exception as e:
        print(f"An unexpected error occurred during message scraping: {e}")
        traceback.print_exc()
        return []

# --- save_to_json Function ---
def save_to_json(data, filename):
    """Saves data to a JSON file."""
    print(f"Attempting to save {len(data)} items to {filename}...")
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Data successfully saved.")
        return True
    except IOError as e:
        print(f"Error: Could not write to file {filename}. Check permissions or path. Details: {e}")
        return False
    except TypeError as e:
         print(f"Error: Data structure is not JSON serializable. Details: {e}")
         return False
    except Exception as e:
        print(f"An unexpected error occurred saving JSON to {filename}: {e}")
        traceback.print_exc()
        return False

# --- Filtering Logic (is_automated_message) ---
def is_automated_message(sender_name, message_content):
    """Checks if a message seems like an automated system message."""
    if not message_content: return False
    sender = sender_name if sender_name else "Me/System"
    text = message_content.strip()
    lower_content = text.lower()

    # Exact system messages (often sender is 'Me/System')
    exact_phrases = [
        "this group was created", "you created this community", "you created this group",
        "missed voice call", "missed video call", "started a call",
        "this message was deleted",
        "messages and calls are end-to-end encrypted. no one outside of this chat, not even whatsapp, can read or listen to them. click to learn more.",
        "messages and calls are end-to-end encrypted.",
        "you joined using this group's invite link",
        "you joined using this community's invite link",
        "[message deleted]", # Handle the scraped deleted text
        "[sticker]", "[empty or unsupported content]", # Handle placeholders if desired
        "[unknown content structure]" # Handle placeholders if desired
    ]
    if lower_content in exact_phrases: return True

    # Actions performed by 'You' (sender is 'Me/System')
    if sender == "Me/System":
        action_keywords_start = [
            "you added", "you removed", "you left", "you joined", "you created", "you changed",
            "you're now an admin", "you are now an admin",
            "you're no longer an admin", "you are no longer an admin"
        ]
        if any(lower_content.startswith(phrase) for phrase in action_keywords_start): return True

        # Other actions where sender is 'Me/System' but subject is named
        # e.g., "You added John Doe" - This is handled by the startsWith check above
        # e.g., "Security code changed."
        if "changed the subject to" in lower_content: return True
        if "changed this group's icon" in lower_content: return True
        if "security code changed" in lower_content: return True
        if "added you" in lower_content: return True # e.g. Someone added you
        if "created the announcement group" in lower_content: return True
        if "updated the community info" in lower_content: return True


    # Actions performed by a specific user (sender name matches start of text)
    else:
        normalized_sender = sender.replace('\u200e', '').strip()
        if lower_content.startswith(normalized_sender.lower()):
             action_part = lower_content[len(normalized_sender):].strip()
             action_verbs = ["added", "removed", "left", "joined", "created group",
                             "changed the subject", "changed this group's icon",
                             "was added", "was removed", # Passive voice
                             "changed their phone number" # Phone change by specific user
                            ]
             if any(action_part.startswith(verb) for verb in action_verbs): return True
        # Check for "<user> was added/removed by <admin>" pattern
        if (f"{normalized_sender.lower()} was added" in lower_content or f"{normalized_sender.lower()} was removed" in lower_content): return True


    # Phone number change (generic message or sender is Me/System)
    if "changed their phone number to a new number." in lower_content: return True
    if "changed to a new number. tap to message or add the new number." in lower_content: return True

    # Polls (if filtering polls)
    # if "poll:" in lower_content: return True

    return False

# --- filter_scraped_json_data Function ---
def filter_scraped_json_data(input_data):
    """Filters a list of message dictionaries (from scraped JSON)."""
    if not isinstance(input_data, list):
        print("Error: Input data for filtering is not a list.")
        return [], 0, 0

    filtered_messages = []
    messages_processed_count = 0
    messages_removed_count = 0

    for msg in input_data:
        messages_processed_count += 1
        sender = msg.get("sender", "Me/System")
        text = msg.get("text", "")

        if not is_automated_message(sender, text):
            filtered_messages.append(msg)
        else:
            messages_removed_count += 1
            # Optional debug print
            # print(f"Filtered out (Auto): Sender='{sender}', Text='{text[:50]}...'")

    messages_kept_count = len(filtered_messages)
    print(f"Filtering complete. Processed: {messages_processed_count}, Kept: {messages_kept_count}, Removed (Auto): {messages_removed_count}")
    return filtered_messages, messages_processed_count, messages_kept_count

# --- run_filter_process_gui Function ---
def run_filter_process_gui():
    """Launches a GUI to select a scraped JSON file and filter it."""
    root = tk.Tk()
    root.withdraw()

    print("Please select the raw scraped JSON file to filter...")
    input_filepath = filedialog.askopenfilename(
        title="Select RAW Scraped WhatsApp JSON File to Filter",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
    )

    if not input_filepath:
        messagebox.showinfo("Cancelled", "No file selected. Filtering cancelled.")
        print("Filtering cancelled by user.")
        return

    try:
        input_dir = os.path.dirname(input_filepath)
        base_name = os.path.basename(input_filepath)
        name_part, _ = os.path.splitext(base_name)
        # Clean up name if it matches standard raw output
        if name_part.lower() == os.path.splitext(RAW_OUTPUT_FILE)[0].lower():
            name_part = "whatsapp_messages" # Generic base

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"{name_part}{FILTERED_OUTPUT_FILE_SUFFIX}_{timestamp}.json"
        output_filepath = os.path.join(input_dir, output_filename)
    except Exception as e:
        messagebox.showerror("Error", f"Could not determine output file path: {e}")
        print(f"Error generating output filename: {e}")
        return

    try:
        print(f"Filtering input file: {input_filepath}")
        print(f"Output will be saved to: {output_filepath}")

        print("Reading input JSON...")
        with open(input_filepath, 'r', encoding='utf-8') as f:
            scraped_data = json.load(f)
        print(f"Read {len(scraped_data)} raw messages.")

        print("Applying filtering rules...")
        filtered_data, processed_count, kept_count = filter_scraped_json_data(scraped_data)

        if save_to_json(filtered_data, output_filepath):
            if kept_count > 0:
                messagebox.showinfo("Success",
                                    f"JSON data filtered successfully!\n"
                                    f"(Automated system messages removed)\n\n"
                                    f"Input: {processed_count} messages\n"
                                    f"Kept: {kept_count} messages\n\n"
                                    f"Saved to:\n{output_filepath}")
                print("Filtering successful.")
            else:
                 messagebox.showwarning("Completed",
                                       f"Filtering complete, but no messages remained after removing automated ones.\n\n"
                                       f"Input: {processed_count} messages\n"
                                       f"An empty list was saved to:\n{output_filepath}")
                 print("Filtering complete, resulted in an empty list.")
        else:
             messagebox.showerror("Error", f"Failed to save filtered data to:\n{output_filepath}\n\nCheck console output for details.")
             print("Failed to save filtered JSON.")

    except FileNotFoundError:
        messagebox.showerror("Error", f"Input JSON file not found:\n{input_filepath}")
        print(f"Error: File not found at {input_filepath}")
    except json.JSONDecodeError as e:
        messagebox.showerror("Error", f"Invalid JSON format in file:\n{input_filepath}\n\nError: {e}")
        print(f"Error: Invalid JSON in {input_filepath}. Details: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during the filtering process: {e}")
        traceback.print_exc()
        messagebox.showerror("Unexpected Error", f"An unexpected error occurred during filtering:\n\n{e}")


# --- Main Execution ---
if __name__ == "__main__":
    print("--- WhatsApp Scraper & Filter (Using Microsoft Edge) ---") # Updated title
    start_time = time.time()
    driver = None
    raw_data_saved = False
    scraping_successful = False

    try:
        print("\n--- Phase 1: Scraping WhatsApp Web using Edge ---") # Updated phase title
        driver = setup_driver() # Setup Edge

        if driver:
            if wait_for_login(driver):
                if find_and_open_chat(driver):
                    scroll_up_to_load_messages(driver)
                    scraped_data = scrape_messages(driver)

                    if scraped_data:
                        if save_to_json(scraped_data, RAW_OUTPUT_FILE):
                             raw_data_saved = True
                             scraping_successful = True
                        else:
                             print(f"CRITICAL WARNING: Failed to save raw scraped data to {RAW_OUTPUT_FILE}")
                    else:
                        print("Scraping finished, but no messages were extracted. No raw data file created.")
                        scraping_successful = True # Allow filtering if old file exists
                else:
                    print("Could not open the target chat. Scraping aborted.")
            else:
                print("Login failed or timed out. Scraping aborted.")
        else:
            print("Edge WebDriver setup failed. Cannot start scraping.") # Updated message

    except Exception as e:
        print(f"\n--- An Unhandled Critical Error Occurred During Scraping Phase ---")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Details: {e}")
        traceback.print_exc()

    finally:
        if driver:
            print("\nClosing Edge WebDriver...") # Updated message
            try:
                driver.quit()
                print("WebDriver closed.")
            except Exception as quit_err:
                print(f"Note: Error occurred while quitting WebDriver: {quit_err}")

    # --- Part 2: Filtering ---
    print("\n--- Phase 2: Filtering Results ---")
    # (Filtering logic remains the same)
    if raw_data_saved:
         print(f"Raw scraped data was saved to: {RAW_OUTPUT_FILE}")
         print("Launching filter tool GUI...")
         run_filter_process_gui()
    elif scraping_successful and os.path.exists(RAW_OUTPUT_FILE):
         print(f"\nScraping completed but no new raw data was saved to {RAW_OUTPUT_FILE} this run.")
         print(f"An existing raw data file was found.")
         try:
             user_choice = input("Do you want to try filtering this existing file? (y/n): ").lower().strip()
             if user_choice == 'y':
                 print("Launching filter tool for existing file...")
                 run_filter_process_gui()
             else:
                 print("Filtering step skipped by user.")
         except EOFError:
              print("No input detected, skipping filtering of existing file.")
    elif os.path.exists(RAW_OUTPUT_FILE):
         print(f"\nScraping phase failed before completion.")
         print(f"An existing raw data file was found: {RAW_OUTPUT_FILE}")
         try:
            user_choice = input("Do you want to try filtering this existing file anyway? (y/n): ").lower().strip()
            if user_choice == 'y':
                 print("Launching filter tool for existing file...")
                 run_filter_process_gui()
            else:
                 print("Filtering step skipped by user.")
         except EOFError:
              print("No input detected, skipping filtering of existing file.")
    else:
         print("\nScraping did not produce a raw data file, and no existing file found.")
         print("Cannot proceed to filtering.")


    end_time = time.time()
    print(f"\nScript finished. Total execution time: {end_time - start_time:.2f} seconds.")

# --- END OF FILE scrapingProgram.py (Edge Version) ---
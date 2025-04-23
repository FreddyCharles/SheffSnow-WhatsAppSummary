# WhatsApp Community Announcement Scraper

This Python script uses Selenium to automate scraping messages from a specified WhatsApp Web "Community Announcement" chat. It saves the raw scraped data and provides an optional GUI tool to filter out common automated system messages (like join/left notifications).

## Overview

The script performs the following actions:

1.  Opens a web browser (Chrome or Edge) controlled by Selenium.
2.  Navigates to WhatsApp Web.
3.  Waits for the user to log in by scanning the QR code, or attempts to reuse a saved browser session.
4.  Searches for and opens a specific chat by its exact name (configured by the user).
5.  Scrolls up multiple times within the chat to load older messages dynamically.
6.  Scrapes the visible messages, extracting the Sender's Name, Message Text, and Timestamp (if available).
7.  Saves the extracted raw data as a list of dictionaries into a JSON file (`whatsapp_messages_raw.json`).
8.  Closes the web browser.
9.  (Optional) If scraping was successful, launches a simple GUI (using Tkinter) prompting the user to select the raw JSON file.
10. (Optional) If a file is selected in the GUI, it filters the data, removing messages identified as automated/system messages.
11. (Optional) Saves the filtered data into a new, timestamped JSON file (e.g., `whatsapp_messages_raw_filtered_YYYYMMDD_HHMMSS.json`).

## Features

*   **Automated Browser Control:** Uses Selenium to interact with WhatsApp Web.
*   **Targeted Chat Scraping:** Finds and scrapes messages from a specific chat name.
*   **Dynamic Loading:** Scrolls up to load more message history.
*   **Data Extraction:** Captures sender, text, and timestamp for each message.
*   **JSON Output:** Stores data in a structured JSON format.
*   **Session Persistence (Optional):** Can attempt to reuse login sessions to avoid frequent QR code scanning.
*   **Automated Message Filtering (Optional):** Includes a GUI tool to remove common system messages (join/left, encryption notices, etc.) from the scraped data. **Note:** This filter is heuristic and does not filter by date.
*   **WebDriver Management:** Uses `webdriver-manager` to automatically handle ChromeDriver/EdgeDriver.

## 1. Prerequisites (What you need before starting)

*   **Python:** Ensure you have Python 3 installed (version 3.6 or higher is recommended). Download from [python.org](https://www.python.org/).
*   **pip:** Python's package installer (usually included with Python).
*   **Web Browser:** Google Chrome or Microsoft Edge installed. The script uses Chrome by default. To use Edge, you'll need to edit the script (search for `# Uncomment for Edge`) and comment out the Chrome-specific lines.
*   **Required Python Libraries:** Open your terminal or command prompt and install the necessary libraries using pip:
    ```bash
    pip install selenium webdriver-manager tk
    ```
    *   `selenium`: For browser automation.
    *   `webdriver-manager`: To automatically manage browser drivers.
    *   `tk`: For the optional GUI file dialog (usually included with Python, but installing ensures it's available).

## 2. Configuration (Tailoring the script)

*   **Open the Script:** Open the `scrapingProgram.py` file in a text editor or IDE.
*   **Set the Chat Name (Crucial):** Find this line near the top:
    ```python
    CHAT_NAME = "SheffSnow Announcements" # <<< --- CHANGE THIS TO THE EXACT CHAT NAME
    ```
    **You MUST change** `"SheffSnow Announcements"` to the **exact, case-sensitive name** of the WhatsApp Community Announcement chat you want to scrape, as it appears in your WhatsApp Web chat list.
*   **(Optional) Adjust Other Settings:**
    *   `SCROLL_COUNT = 15`: Increase this number to scroll up further and load more older messages. Decrease it for fewer messages.
    *   `USE_SAVED_SESSION = True`:
        *   `True` (Default): The script will try to create/use a folder named `whatsapp_session` in the same directory to store your login cookies. After the first successful QR scan, subsequent runs *might* log you in automatically.
        *   `False`: The script will always require you to scan the QR code and won't save session data.
    *   `RAW_OUTPUT_FILE = "whatsapp_messages_raw.json"`: Change the name for the raw output file if desired.
    *   `FILTERED_OUTPUT_FILE_SUFFIX = "_filtered"`: Change the suffix added to the filtered output filename if desired.
    *   `USER_DATA_DIR = "whatsapp_session"`: The folder name for saved session data (usually no need to change).

## 3. Running the Script

*   **Navigate to Directory:** Open your terminal or command prompt. Use the `cd` command to navigate to the folder where you saved `scrapingProgram.py`.
*   **Execute:** Run the script using Python:
    ```bash
    python scrapingProgram.py
    ```

## 4. Interaction During Execution

*   **Browser Opens:** A Chrome (or Edge, if modified) browser window will open automatically and navigate to `https://web.whatsapp.com`.
*   **Login / QR Code Scan:**
    *   **Monitor the Terminal:** Check the output messages.
    *   **If `USE_SAVED_SESSION` is `True` and a valid session exists:** The script might log you in automatically (terminal shows "Logged in using saved session.").
    *   **If `USE_SAVED_SESSION` is `False` or no valid session exists:**
        *   The terminal will show "Please scan the QR code...".
        *   A QR code will appear in the browser window.
        *   **Action:** Open WhatsApp on your phone, go to `Settings` > `Linked Devices` > `Link a Device`, and scan the QR code within the timeout (default 120 seconds).
    *   Wait for the terminal to show "Login successful!".
*   **Automatic Scraping:**
    *   **Do not interact with the browser window.**
    *   The script will automatically search for the `CHAT_NAME`, click it, scroll up `SCROLL_COUNT` times, and scrape the messages.
    *   Monitor the terminal for progress (searching, scrolling, scraping...).
*   **Browser Closes:** After scraping finishes and saves the raw data, the browser window will close automatically.

## 5. Filtering the Data (Optional GUI Step)

*   **Condition:** This step only occurs *after* the browser has closed and *if* the raw data was successfully saved to `whatsapp_messages_raw.json`.
*   **File Dialog Appears:** A small "Select Scraped WhatsApp JSON File to Filter" window will pop up.
*   **Select File:** Navigate to the directory (it should default there), select the `whatsapp_messages_raw.json` file, and click "Open".
*   **Processing:** The script reads the raw JSON and filters out messages identified as automated (join/left, encryption notices, etc.) based on text patterns. **It does not filter by date.**
*   **Result Message:** A message box will appear:
    *   **Success:** Shows how many messages were processed/kept and the name of the *new* filtered file (e.g., `whatsapp_messages_raw_filtered_YYYYMMDD_HHMMSS.json`). Click "OK".
    *   **Warning/Completed (Empty):** Informs you if filtering removed *all* messages. An empty file will still be saved. Click "OK".
    *   **Error:** Indicates a problem during filtering (e.g., invalid file, save error). Check the terminal output for more details. Click "OK".

## 6. Understanding the Output Files

After a successful run, you will find these files in the script's directory:

*   **`whatsapp_messages_raw.json`:** Contains the *complete*, unfiltered data scraped directly from the chat. Each message is a dictionary:
    ```json
    {
        "sender": "Sender Name",
        "text": "The message content.",
        "timestamp": "10:45" // Or "Yesterday", "DD/MM/YYYY", etc.
    }
    ```
    *(System messages might have `sender` as `"Me/System"`).*
*   **`whatsapp_messages_raw_filtered_YYYYMMDD_HHMMSS.json`:** (Timestamp varies) Contains the messages *after* the optional filtering step removed automated system messages. Has the same format as the raw file. This file is only created if the filtering step is completed.
*   **`whatsapp_session` (Folder):** Created only if `USE_SAVED_SESSION = True`. Stores browser session data to potentially allow automatic logins on future runs. Can be safely deleted to force a fresh QR scan.

## Important Notes & Troubleshooting

*   **XPATH Selectors May Break:** WhatsApp Web frequently updates its structure. If the script suddenly fails to find elements (search box, chat link, messages), the `XPATH` locators defined near the top of the script probably need updating. You'll need to use your browser's Developer Tools (usually F12) on `web.whatsapp.com` to inspect the elements and find the new correct XPaths or CSS Selectors.
*   **Filter Accuracy:** The `is_automated_message` function uses common text patterns. It might sometimes misclassify a message (either remove a real one or keep an automated one). Review the filtered output. You may need to adjust the patterns within the `is_automated_message` function in the script if you notice consistent errors for your specific chat's system messages.
*   **No Date Filtering:** The script **does not filter messages by date**. Timestamps scraped from WhatsApp Web are often relative (e.g., "10:45", "Yesterday") and not easily usable for date-range filtering without complex reconstruction logic (which is not included).
*   **Ethical Use:** Use this script responsibly. Excessive scraping might violate WhatsApp's Terms of Service or flag your account. Respect user privacy.
*   **Check Terminal Output:** Error messages and progress are printed to the terminal. Refer to these messages first if the script doesn't behave as expected.

## License

This project is released under the MIT License. (Or specify your preferred license).
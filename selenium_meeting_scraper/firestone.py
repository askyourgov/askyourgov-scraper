"""Firestone-specific scraper implementation"""
from .base import Scraper
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urljoin, urlparse, parse_qs, unquote
import time
import re
from datetime import datetime

BASE_URL = "https://firestoneco.portal.civicclerk.com"
API_BASE_URL = "https://firestoneco.api.civicclerk.com/v1/"


def extract_meeting_date(link_element):
    """Extract meeting date from the link element
    
    Looks for date in:
    - aria-label attribute (e.g., "Board of Trustees event on Wednesday, Aug. 13, 2025 6:00 PM")
    - h2 element with date (e.g., "Aug 13, <br>2025")
    - data-date attribute on the link
    """
    try:
        # Try data-date attribute first (ISO format: "2025-08-13T18:00:00Z")
        data_date = link_element.get_attribute("data-date")
        if data_date:
            try:
                # Parse ISO format: "2025-08-13T18:00:00Z"
                date_obj = datetime.fromisoformat(data_date.replace('Z', '+00:00'))
                return date_obj.date()
            except:
                pass
        
        # Try aria-label attribute
        aria_label = link_element.get_attribute("aria-label")
        if aria_label:
            # Extract date from aria-label: "Board of Trustees event on Wednesday, Aug. 13, 2025 6:00 PM"
            date_match = re.search(r'([A-Za-z]+),?\s+([A-Za-z]+)\.?\s+(\d+),?\s+(\d{4})', aria_label)
            if date_match:
                month_name = date_match.group(2)
                day = int(date_match.group(3))
                year = int(date_match.group(4))
                
                # Convert month name to number
                month_map = {
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                }
                month = month_map.get(month_name.lower()[:3])
                if month:
                    return datetime(year, month, day).date()
        
        # Try h2 element with date
        try:
            date_div = link_element.find_element(By.CSS_SELECTOR, "div[data-testid='dateDetails']")
            h2 = date_div.find_element(By.CSS_SELECTOR, "h2.MuiTypography-h5")
            date_text = h2.text.strip()
            # Parse "Aug 13, 2025" format
            date_match = re.search(r'([A-Za-z]+)\s+(\d+),?\s+(\d{4})', date_text)
            if date_match:
                month_name = date_match.group(1)
                day = int(date_match.group(2))
                year = int(date_match.group(3))
                
                month_map = {
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                }
                month = month_map.get(month_name.lower()[:3])
                if month:
                    return datetime(year, month, day).date()
        except:
            pass
        
        return None
    except Exception as e:
        return None


def get_js_source(driver):
    """Fetch and analyze the JavaScript source code"""
    try:
        # Get all script tags
        scripts = driver.execute_script("""
            const scripts = [];
            document.querySelectorAll('script[src]').forEach(script => {
                scripts.push({
                    src: script.src,
                    type: script.type,
                    async: script.async,
                    defer: script.defer
                });
            });
            return scripts;
        """)
        
        # Find the main bundle (usually main.{hash}.js)
        main_script = None
        for script in scripts:
            if 'main.' in script['src'] and script['src'].endswith('.js'):
                main_script = script['src']
                break
        
        return main_script, scripts
    except Exception as e:
        print(f"  ⚠️  Could not get JS source info: {e}")
        return None, []


def extract_react_data(driver):
    """Extract data from React component state using React DevTools"""
    try:
        # Try to access React DevTools API
        react_data = driver.execute_script("""
            // Try to find React root
            function findReactRoot(element) {
                for (let key in element) {
                    if (key.startsWith('__reactInternalInstance') || key.startsWith('__reactFiber')) {
                        return element[key];
                    }
                }
                return null;
            }
            
            // Get React root from document
            const root = document.getElementById('root');
            if (!root) return null;
            
            const reactRoot = findReactRoot(root);
            if (!reactRoot) return null;
            
            // Try to extract component state/props
            function extractComponentData(fiber) {
                if (!fiber) return null;
                
                const data = {
                    type: fiber.type?.name || fiber.type?.displayName || 'Unknown',
                    props: fiber.memoizedProps || fiber.pendingProps || {},
                    state: fiber.memoizedState || null
                };
                
                return data;
            }
            
            return extractComponentData(reactRoot);
        """)
        return react_data
    except Exception as e:
        print(f"  ⚠️  Could not extract React data: {e}")
        return None


def inspect_button_handlers(driver, element):
    """Inspect JavaScript event handlers on an element"""
    try:
        handlers = driver.execute_script("""
            const element = arguments[0];
            const handlers = {};
            
            // Get all event listeners (if available)
            if (element.onclick) {
                handlers.onclick = element.onclick.toString();
            }
            
            // Get data attributes
            handlers.dataAttributes = {};
            for (let attr of element.attributes) {
                if (attr.name.startsWith('data-')) {
                    handlers.dataAttributes[attr.name] = attr.value;
                }
            }
            
            // Get React props if available - walk up the fiber tree to find DownloadFileButton
            handlers.reactProps = null;
            handlers.remoteFile = null;
            
            function findReactFiber(element) {
                for (let key in element) {
                    if (key.startsWith('__reactInternalInstance') || key.startsWith('__reactFiber')) {
                        return element[key];
                    }
                }
                return null;
            }
            
            function findComponentWithRemoteFile(fiber, depth = 0) {
                if (!fiber || depth > 10) return null;
                
                // Check if this is DownloadFileButton component
                if (fiber.type && fiber.type.displayName === 'DownloadFileButton') {
                    if (fiber.memoizedProps && fiber.memoizedProps.remoteFile) {
                        return fiber.memoizedProps.remoteFile;
                    }
                }
                
                // Check props for remoteFile
                if (fiber.memoizedProps && fiber.memoizedProps.remoteFile) {
                    return fiber.memoizedProps.remoteFile;
                }
                
                // Walk up the tree
                if (fiber.return) {
                    return findComponentWithRemoteFile(fiber.return, depth + 1);
                }
                
                return null;
            }
            
            const fiber = findReactFiber(element);
            if (fiber) {
                handlers.reactProps = fiber.memoizedProps || fiber.pendingProps || null;
                handlers.remoteFile = findComponentWithRemoteFile(fiber);
            }
            
            return handlers;
        """, element)
        return handlers
    except Exception as e:
        print(f"  ⚠️  Could not inspect handlers: {e}")
        return None


def build_download_url(remote_file, is_attachment=False, plain_text=False):
    """Build download URL from remoteFile data based on component logic.
    
    According to the component code:
    - If remoteFile.streamUrl exists, use it directly (Azure Blob Storage with SAS tokens)
    - Otherwise, construct API URL based on file type:
      - Attachments: Meetings/GetAttachmentFile(fileId={fileId})
      - Meeting files: Meetings/GetMeetingFileStream(fileId={fileId},plainText={true/false})
    """
    if not remote_file:
        return None
    
    file_id = remote_file.get('fileId')
    if not file_id:
        return None
    
    # Check if there's a streamUrl (direct Azure Blob Storage URL with SAS tokens)
    # This takes precedence over API URL construction
    stream_url = remote_file.get('streamUrl')
    if stream_url:
        # streamUrl is a direct Azure Blob Storage URL, return as-is
        return stream_url
    
    # Construct API URL if no streamUrl
    if is_attachment:
        # Attachment files use GetAttachmentFile
        return f"{API_BASE_URL}Meetings/GetAttachmentFile(fileId={file_id})"
    else:
        # Meeting files use GetMeetingFileStream
        return f"{API_BASE_URL}Meetings/GetMeetingFileStream(fileId={file_id},plainText={str(plain_text).lower()})"


def enable_network_logging(driver):
    """Enable Chrome DevTools Protocol network logging to capture download URLs"""
    try:
        # Enable Network domain
        driver.execute_cdp_cmd('Network.enable', {})
        return True
    except Exception as e:
        print(f"  ⚠️  Could not enable network logging: {e}")
        return False


def get_network_response_url(driver, timeout=5):
    """Get the last network response URL (for capturing downloads)"""
    try:
        # Get performance logs
        logs = driver.get_log('performance')
        for log in reversed(logs):  # Check most recent first
            message = log.get('message', '{}')
            import json
            log_data = json.loads(message)
            message_data = log_data.get('message', {})
            
            # Check for network response
            if message_data.get('method') == 'Network.responseReceived':
                response = message_data.get('params', {}).get('response', {})
                url = response.get('url', '')
                mime_type = response.get('mimeType', '')
                
                # Check if it's a PDF or document download
                if 'pdf' in mime_type.lower() or 'application/pdf' in mime_type.lower():
                    return url
                # Check if it's a download URL
                if 'GetMeetingFileStream' in url or 'download' in url.lower():
                    return url
        return None
    except Exception as e:
        return None


class FirestoneScraper(Scraper):
    """Firestone-specific scraper implementation"""
    
    def __init__(self):
        """Initialize Firestone scraper"""
        super().__init__(BASE_URL)
    
    def scrape_meetings(self):
        """Scrape list of meetings from Firestone portal"""
        # --- Configure Chrome ---
        options = self.get_chrome_options(headless=True)

        # --- Launch browser ---
        driver = webdriver.Chrome(options=options)
        
        # Execute script to remove webdriver property
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            '''
        })
        
        driver.get(self.base_url)

        try:
            # Wait for React app to load - wait for the root div to have content
            wait = WebDriverWait(driver, 30)
            
            # Wait for the event list table to appear (React needs time to render)
            event_div = wait.until(
                EC.presence_of_element_located((By.ID, "event-list-table"))
            )
            print("✅ Found event-list-table element")

            # Find the ul with id="Event-list" within the div
            event_list_ul = wait.until(
                EC.presence_of_element_located((By.ID, "Event-list"))
            )
            print(f"✅ Found Event-list ul element")

            # Wait for at least one meeting item to appear (ensures React has rendered content)
            wait.until(
                lambda d: len(event_list_ul.find_elements(By.CSS_SELECTOR, "li.MuiListItem-container a[href]")) > 0
            )
            
            # Get all li elements within the ul and filter to only those with anchor tags
            # This skips listSubheader li elements (like "Past Events")
            all_li = event_list_ul.find_elements(By.CSS_SELECTOR, "li.MuiListItem-container")
            li_elements = [li for li in all_li if len(li.find_elements(By.CSS_SELECTOR, "a[href]")) > 0]
            
            print(f"✅ Found {len(li_elements)} meeting items (filtered from {len(all_li)} total li elements)")

            meetings = []
            for i, li in enumerate(li_elements):
                try:
                    # Find the anchor tag within the li - use find_elements to check if it exists
                    links = li.find_elements(By.CSS_SELECTOR, "a[href]")
                    if not links:
                        # Skip this li - it's probably a listSubheader
                        continue
                    
                    link = links[0]
                    
                    # Extract href
                    href = link.get_attribute("href")
                    if not href:
                        continue
                    
                    # Extract data-id (event ID)
                    event_id = link.get_attribute("data-id")
                    
                    # Extract title from the h3 element with id like "eventListRow-{id}-title"
                    title = ""
                    try:
                        title_element = link.find_element(By.CSS_SELECTOR, "h3[id^='eventListRow-'][id$='-title']")
                        title = title_element.text.strip()
                    except:
                        # Fallback: try to get text from the link itself
                        title = link.text.strip()
                    
                    # Extract meeting date
                    meeting_date = extract_meeting_date(link)
                    
                    # Build full URL
                    full_url = urljoin(self.base_url, href) if not href.startswith("http") else href
                    meetings.append({
                        "event_id": event_id,
                        "title": title,
                        "url": full_url,
                        "href": href,
                        "date": meeting_date
                    })
                except Exception as e:
                    print(f"⚠️  Warning: Could not extract meeting from li[{i}]: {e}")
                    continue

            print(f"\n✅ Found {len(meetings)} meetings:")
            for m in meetings:
                date_str = m['date'].strftime('%Y-%m-%d') if m.get('date') else 'Unknown date'
                print(f"- [{m['event_id']}] {m['title']} ({date_str})")
                print(f"  URL: {m['url']}")
                print()
            
            return meetings

        except Exception as e:
            print(f"❌ Error scraping meetings: {e}")
            print(f"   Error type: {type(e).__name__}")
            
            # Try to get more details about Selenium errors
            if hasattr(e, 'msg') and e.msg:
                print(f"   Error message: {e.msg}")
            elif str(e):
                print(f"   Error details: {str(e)}")
            else:
                print(f"   (No error message available)")
            
            # Try to get page info if driver exists
            try:
                if 'driver' in locals() and driver:
                    current_url = driver.current_url
                    print(f"   Current URL: {current_url}")
                    page_title = driver.title
                    print(f"   Page title: {page_title}")
            except Exception as debug_e:
                print(f"   Could not get page info: {debug_e}")
            
            import traceback
            print(f"   Full traceback:")
            traceback.print_exc()
            return []
        finally:
            driver.quit()
    
    def scrape_meeting_files(self, driver, meeting_url, event_id, enable_network_monitoring=False):
        """Scrape all files from a meeting's /files page"""
        print(f"\n📄 Scraping files for event {event_id}...")
        
        wait = WebDriverWait(driver, 20)
        
        # Enable network monitoring if requested
        if enable_network_monitoring:
            enable_network_logging(driver)
        
        # Navigate to the files page
        files_url = urljoin(self.base_url, f"/event/{event_id}/files")
        driver.get(files_url)
        
        # Wait for the files list to load
        try:
            wait.until(
                EC.presence_of_element_located((By.ID, "files"))
            )
            time.sleep(2)  # Wait for React to fully render
            print("✅ Files page loaded")
        except:
            print("⚠️  Could not find files list")
            return []
        
        # Get JavaScript source info
        main_js, all_scripts = get_js_source(driver)
        if main_js:
            print(f"  📜 Main JS bundle: {main_js}")
            print(f"     (You can fetch this to analyze the component structure)")
        
        # Try to extract React data
        react_data = extract_react_data(driver)
        if react_data:
            print(f"  📊 React root component: {react_data.get('type', 'Unknown')}")
        
        files = []
        
        # Get main files (Agenda, Agenda Packet)
        try:
            files_list = driver.find_element(By.ID, "files")
            file_items = files_list.find_elements(By.CSS_SELECTOR, "li.MuiListItem-container")
            
            for item in file_items:
                try:
                    # Get file name
                    file_name_elem = item.find_element(By.CSS_SELECTOR, "span.MuiListItemText-primary")
                    file_name = file_name_elem.text.strip()
                    
                    # Get download button
                    try:
                        download_btn = item.find_element(By.CSS_SELECTOR, "button[data-testid='files']")
                        download_btn_id = download_btn.get_attribute("id")
                        
                        print(f"    🔍 Debug main file {file_name}: download_btn_id={download_btn_id}")
                        
                        # Inspect the button's handlers and data to get remoteFile
                        handlers = inspect_button_handlers(driver, download_btn)
                        remote_file = None
                        
                        print(f"    🔍 Debug main file {file_name}: handlers={list(handlers.keys()) if handlers else None}")
                        
                        if handlers:
                            # Check if we found remoteFile in React props
                            if handlers.get('remoteFile'):
                                remote_file = handlers['remoteFile']
                                file_id = remote_file.get('fileId')
                                file_type = remote_file.get('fileType')
                                file_name = remote_file.get('name')
                                stream_url = remote_file.get('streamUrl')
                                
                                print(f"  ✅ Found remoteFile: fileId={file_id}, fileType={file_type}, name={file_name}")
                                if stream_url:
                                    print(f"     📎 Has streamUrl (direct Azure Blob Storage URL)")
                            elif handlers.get('reactProps'):
                                # Try to get remoteFile from props
                                props = handlers['reactProps']
                                if props and 'remoteFile' in props:
                                    remote_file = props['remoteFile']
                                    if remote_file.get('streamUrl'):
                                        print(f"     📎 Has streamUrl (direct Azure Blob Storage URL)")
                        
                        # Click to open menu
                        download_btn.click()
                        time.sleep(0.8)  # Wait for menu to open
                        
                        # Find the menu and extract download links
                        menu = wait.until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, f"#{download_btn_id}-menu"))
                        )
                        menu_items = menu.find_elements(By.CSS_SELECTOR, "li[role='menuitem']")
                        
                        for menu_item in menu_items:
                            try:
                                file_type = menu_item.find_element(By.CSS_SELECTOR, "span.MuiListItemText-primary").text.strip()
                                
                                # Inspect menu item to find DownloadFileButton component
                                download_elem = menu_item.find_element(By.CSS_SELECTOR, "span[data-testid='downloadFileButton']")
                                item_handlers = inspect_button_handlers(driver, download_elem)
                                
                                # Try to get remoteFile from the DownloadFileButton component
                                menu_remote_file = None
                                if item_handlers and item_handlers.get('remoteFile'):
                                    menu_remote_file = item_handlers['remoteFile']
                                elif item_handlers and item_handlers.get('reactProps'):
                                    props = item_handlers['reactProps']
                                    if props and 'remoteFile' in props:
                                        menu_remote_file = props['remoteFile']
                                
                                # Use remoteFile from menu item if found, otherwise use the one from parent
                                file_data = menu_remote_file or remote_file
                                
                                # Debug: Print what we found
                                if not file_data:
                                    print(f"    ⚠️  No remoteFile found for {file_name}")
                                    if item_handlers:
                                        print(f"       Handlers keys: {list(item_handlers.keys())}")
                                        if item_handlers.get('reactProps'):
                                            print(f"       React props keys: {list(item_handlers['reactProps'].keys()) if isinstance(item_handlers['reactProps'], dict) else 'Not a dict'}")
                                
                                # Determine if it's plain text based on menu item text
                                plain_text = "Plain Text" in file_type
                                
                                # Build download URL
                                download_url = None
                                file_id = None
                                
                                if file_data:
                                    file_id = file_data.get('fileId')
                                    file_type_code = file_data.get('fileType', 1)  # 1 = agendaItem, 3 = attachment
                                    is_attachment = (file_type_code == 3)
                                    
                                    # Build URL based on component logic
                                    download_url = build_download_url(file_data, is_attachment, plain_text)
                                
                                # Fallback: if we still don't have a URL, try checking iframe (if already loaded)
                                if not download_url or download_url == "N/A":
                                    try:
                                        # Check if iframe is already loaded (might be from previous interaction)
                                        iframe = driver.find_element(By.ID, "pdfViewerIframe")
                                        iframe_src = iframe.get_attribute("src")
                                        if iframe_src and "fileId" in iframe_src:
                                            parsed = urlparse(iframe_src)
                                            query = parse_qs(parsed.query)
                                            if "file" in query:
                                                file_url = unquote(query["file"][0])
                                                match = re.search(r'fileId=(\d+)', file_url)
                                                if match:
                                                    file_id = match.group(1)
                                                    plain_text = "plainText=true" in file_url
                                                    download_url = f"{API_BASE_URL}Meetings/GetMeetingFileStream(fileId={file_id},plainText={str(plain_text).lower()})"
                                                else:
                                                    download_url = file_url
                                    except:
                                        # Iframe not available - try one more thing: look for download link in DOM
                                        try:
                                            # Try to find an <a> tag with download attribute or href pointing to file
                                            download_links = driver.find_elements(By.CSS_SELECTOR, "a[download], a[href*='GetMeetingFileStream'], a[href*='download']")
                                            if download_links:
                                                download_url = download_links[0].get_attribute('href')
                                                print(f"    ✅ Found download link in DOM: {download_url[:80]}...")
                                        except:
                                            pass
                                        
                                        if not download_url or download_url == "N/A":
                                            print(f"    ⚠️  Could not extract download URL from any source")
                                            download_url = "N/A"
                                
                                file_info = {
                                    "name": file_name,
                                    "type": file_type,
                                    "download_url": download_url or "N/A",
                                    "file_id": file_id,
                                    "plain_text": plain_text,
                                    "has_stream_url": bool(file_data and file_data.get('streamUrl')) if file_data else False
                                }
                                files.append(file_info)
                                
                                # Print file info to terminal
                                print(f"    📄 {file_info['name']}")
                                print(f"       Type: {file_info['type']}")
                                print(f"       URL: {file_info['download_url']}")
                                if file_info['file_id']:
                                    print(f"       File ID: {file_info['file_id']}")
                                if file_info.get('has_stream_url'):
                                    print(f"       ⭐ Direct Azure Blob Storage URL")
                                print()
                                
                                # Close menu by clicking outside
                                driver.execute_script("arguments[0].click();", driver.find_element(By.TAG_NAME, "body"))
                                time.sleep(0.3)
                                break  # Only get first menu item for now
                                
                            except Exception as e:
                                print(f"    ⚠️  Error processing menu item: {e}")
                                pass
                        
                    except:
                        # No download button, just add the file name
                        files.append({
                            "name": file_name,
                            "type": "Unknown",
                            "download_url": "N/A"
                        })
                    
                except Exception as e:
                    print(f"  ⚠️  Error extracting file: {e}")
                    continue
        except Exception as e:
            print(f"  ⚠️  Error processing main files: {e}")
        
        # Get attachments - full version with download button extraction
        try:
            # Wait for attachments list to load
            attachments_list = wait.until(
                EC.presence_of_element_located((By.ID, "AttachmentsList"))
            )
            # Get all list items including headers
            all_items = attachments_list.find_elements(By.CSS_SELECTOR, "li")
            
            current_section = None
            
            for item in all_items:
                try:
                    # Check if this is a section header
                    section_header = item.find_elements(By.CSS_SELECTOR, ".MuiListSubheader-root span")
                    if section_header and section_header[0].text.strip():
                        current_section = section_header[0].text.strip()
                        continue
                    
                    # Check if this is a file item (button or list item)
                    file_name_elem = item.find_elements(By.CSS_SELECTOR, "span.MuiListItemText-primary")
                    if file_name_elem:
                        file_name = file_name_elem[0].text.strip()
                        
                        # Try to find download button (could be reportFiles or attachmentFiles)
                        download_btn = None
                        download_btn_type = None
                        
                        try:
                            download_btn = item.find_element(By.CSS_SELECTOR, "button[data-testid='reportFiles']")
                            download_btn_type = "reportFiles"
                        except:
                            try:
                                download_btn = item.find_element(By.CSS_SELECTOR, "button[data-testid='attachmentFiles']")
                                download_btn_type = "attachmentFiles"
                            except:
                                pass
                        
                        if download_btn:
                            download_btn_id = download_btn.get_attribute("id")
                            
                            print(f"    🔍 Debug attachment {file_name}: download_btn_id={download_btn_id}, type={download_btn_type}")
                            
                            # Inspect button to get remoteFile data
                            handlers = inspect_button_handlers(driver, download_btn)
                            remote_file = None
                            
                            print(f"    🔍 Debug attachment {file_name}: handlers={list(handlers.keys()) if handlers else None}")
                            
                            if handlers and handlers.get('remoteFile'):
                                remote_file = handlers['remoteFile']
                                print(f"    ✅ Found remoteFile in handlers for {file_name}")
                            elif handlers and handlers.get('reactProps'):
                                props = handlers['reactProps']
                                if props and 'remoteFile' in props:
                                    remote_file = props['remoteFile']
                                    print(f"    ✅ Found remoteFile in reactProps for {file_name}")
                                else:
                                    print(f"    ⚠️  No remoteFile in reactProps for {file_name}")
                                    if props:
                                        print(f"       Props keys: {list(props.keys()) if isinstance(props, dict) else type(props)}")
                            else:
                                print(f"    ⚠️  No handlers or no remoteFile for {file_name}")
                            
                            # Click to open menu
                            download_btn.click()
                            time.sleep(0.8)
                            
                            try:
                                # Find the menu
                                menu = wait.until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, f"#{download_btn_id}-menu"))
                                )
                                menu_items = menu.find_elements(By.CSS_SELECTOR, "li[role='menuitem']")
                                
                                # Process each menu item (PDF, Plain Text, etc.)
                                for menu_item in menu_items:
                                    try:
                                        file_type_text = menu_item.find_element(By.CSS_SELECTOR, "span.MuiListItemText-primary").text.strip()
                                        
                                        # Find the download button in the menu item
                                        download_elem = menu_item.find_element(By.CSS_SELECTOR, "span[data-testid='downloadFileButton']")
                                        
                                        # Try to get remoteFile from menu item
                                        item_handlers = inspect_button_handlers(driver, download_elem)
                                        menu_remote_file = None
                                        
                                        print(f"      🔍 Debug menu item {file_type_text}: item_handlers={list(item_handlers.keys()) if item_handlers else None}")
                                        
                                        if item_handlers and item_handlers.get('remoteFile'):
                                            menu_remote_file = item_handlers['remoteFile']
                                            print(f"      ✅ Found remoteFile in menu item handlers")
                                        elif item_handlers and item_handlers.get('reactProps'):
                                            props = item_handlers['reactProps']
                                            print(f"      🔍 Menu item reactProps keys: {list(props.keys()) if isinstance(props, dict) else type(props)}")
                                            if props and 'remoteFile' in props:
                                                menu_remote_file = props['remoteFile']
                                                print(f"      ✅ Found remoteFile in menu item reactProps")
                                            else:
                                                print(f"      ⚠️  No remoteFile in menu item reactProps")
                                        else:
                                            print(f"      ⚠️  No item_handlers for menu item")
                                        
                                        # Use menu item's remoteFile if available, otherwise use parent's
                                        file_data = menu_remote_file or remote_file
                                        
                                        print(f"      🔍 Final file_data for {file_name}: {file_data}")
                                        
                                        # Determine if it's plain text
                                        plain_text = "Plain Text" in file_type_text
                                        
                                        file_id = file_data.get('fileId') if file_data else None
                                        file_type_code = file_data.get('fileType', 3) if file_data else 3  # Default to attachment
                                        is_attachment = (file_type_code == 3)
                                        
                                        # Build download URL for reference
                                        download_url = None
                                        if file_data:
                                            download_url = build_download_url(file_data, is_attachment, plain_text)
                                            print(f"      ✅ Built download URL: {download_url[:80]}...")
                                        else:
                                            print(f"      ⚠️  No file_data to build URL")
                                        
                                        # Debug: Print what we're storing
                                        if not download_url or download_url == "N/A":
                                            print(f"    ⚠️  No download URL for {file_name} (file_id={file_id}, is_attachment={is_attachment})")
                                        
                                        files.append({
                                            "name": file_name,
                                            "type": file_type_text,
                                            "section": current_section,
                                            "download_url": download_url or "N/A",
                                            "file_id": file_id,
                                            "plain_text": plain_text,
                                            "is_attachment": is_attachment,
                                            "download_button_id": download_btn_id,
                                            "download_button_type": download_btn_type,
                                            "file_name_text": file_name,  # Store for matching later
                                            "file_data": file_data  # Store raw file_data for debugging
                                        })
                                    except Exception as e:
                                        print(f"    ⚠️  Error processing menu item: {e}")
                                        continue
                                
                                # Close menu
                                driver.execute_script("arguments[0].click();", driver.find_element(By.TAG_NAME, "body"))
                                time.sleep(0.3)
                            except Exception as e:
                                print(f"    ⚠️  Error opening menu for {file_name}: {e}")
                                # Close menu if open
                                try:
                                    driver.execute_script("arguments[0].click();", driver.find_element(By.TAG_NAME, "body"))
                                except:
                                    pass
                        else:
                            # File item without download button - just add the name
                            files.append({
                                "name": file_name,
                                "type": "Attachment",
                                "section": current_section,
                                "download_url": "N/A"
                            })
                    
                except Exception as e:
                    continue
        except Exception as e:
            print(f"  ⚠️  Error processing attachments: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"  ✅ Found {len(files)} files")
        return files
    
    def _download_files_via_clicks(self, driver, meeting, meeting_download_dir):
        """Download files by clicking download buttons"""
        print(f"   📥 Clicking download buttons (files will be saved to {meeting_download_dir})...")
        
        # Navigate to files page to click buttons
        files_url = urljoin(self.base_url, f"/event/{meeting['event_id']}/files")
        driver.get(files_url)
        time.sleep(3)  # Wait for page to load
        
        # Wait for files list and attachments list
        wait = WebDriverWait(driver, 20)
        try:
            wait.until(EC.presence_of_element_located((By.ID, "files")))
            wait.until(EC.presence_of_element_located((By.ID, "AttachmentsList")))
            time.sleep(2)  # Extra wait for React to render
        except:
            print(f"   ⚠️  Could not load files page")
            return
        
        # Find all download buttons on the page and click them
        print(f"   🔍 Finding all download buttons on page...")
        
        # Find all download buttons in main files list
        main_files_buttons = []
        try:
            files_list = driver.find_element(By.ID, "files")
            list_items = files_list.find_elements(By.CSS_SELECTOR, "li.MuiListItem-container")
            for item in list_items:
                try:
                    file_name_elem = item.find_element(By.CSS_SELECTOR, "span.MuiListItemText-primary")
                    file_name = file_name_elem.text.strip()
                    download_btn = item.find_element(By.CSS_SELECTOR, "button[data-testid='files']")
                    main_files_buttons.append((file_name, download_btn))
                except:
                    continue
        except:
            pass
        
        # Find all download buttons in attachments list
        attachment_buttons = []
        try:
            attachments_list = driver.find_element(By.ID, "AttachmentsList")
            all_items = attachments_list.find_elements(By.CSS_SELECTOR, "li")
            for item in all_items:
                try:
                    # Skip section headers
                    if item.find_elements(By.CSS_SELECTOR, ".MuiListSubheader-root"):
                        continue
                    
                    # Skip "No Attachment File" items
                    name_elems = item.find_elements(By.CSS_SELECTOR, "span.MuiListItemText-primary")
                    if not name_elems:
                        continue
                    file_name = name_elems[0].text.strip()
                    
                    if 'No Attachment File' in file_name:
                        continue
                    
                    # Try to find download button (either attachmentFiles or reportFiles)
                    download_btn = None
                    for btn_type in ['attachmentFiles', 'reportFiles']:
                        try:
                            download_btn = item.find_element(By.CSS_SELECTOR, f"button[data-testid='{btn_type}']")
                            break
                        except:
                            continue
                    
                    if download_btn:
                        attachment_buttons.append((file_name, download_btn))
                except:
                    continue
        except:
            pass
        
        all_buttons = main_files_buttons + attachment_buttons
        print(f"   ✅ Found {len(all_buttons)} downloadable files")
        
        # Click each download button
        for idx, (file_name, download_btn) in enumerate(all_buttons, 1):
            print(f"   [{idx}/{len(all_buttons)}] 📥 Downloading: {file_name}")
            try:
                # Scroll button into view
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", download_btn)
                time.sleep(0.5)
                
                # Click the download button to open menu
                download_btn.click()
                time.sleep(1.5)  # Wait for menu to appear
                
                # Find the menu (it should have an ID based on the button ID)
                download_btn_id = download_btn.get_attribute("id")
                if download_btn_id:
                    menu = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, f"#{download_btn_id}-menu")))
                    menu_items = menu.find_elements(By.CSS_SELECTOR, "li[role='menuitem']")
                    
                    if menu_items:
                        # Click the first menu item (usually PDF)
                        menu_item = menu_items[0]
                        download_span = menu_item.find_element(By.CSS_SELECTOR, "span[data-testid='downloadFileButton']")
                        print(f"      ✅ Clicking download in menu...")
                        download_span.click()
                        time.sleep(3)  # Wait for download to start
                        print(f"      ✅ Download started")
                    else:
                        print(f"      ⚠️  No menu items found")
                    
                    # Close menu
                    try:
                        driver.execute_script("arguments[0].click();", driver.find_element(By.TAG_NAME, "body"))
                        time.sleep(0.5)
                    except:
                        pass
                else:
                    print(f"      ⚠️  Button has no ID")
            except Exception as e:
                print(f"      ⚠️  Error: {e}")
                # Close menu if it opened
                try:
                    driver.execute_script("arguments[0].click();", driver.find_element(By.TAG_NAME, "body"))
                    time.sleep(0.5)
                except:
                    pass


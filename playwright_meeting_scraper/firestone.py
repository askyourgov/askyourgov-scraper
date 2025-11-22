"""Firestone-specific scraper implementation using Playwright"""
from .base import Scraper
from playwright.sync_api import Page, sync_playwright
from urllib.parse import urljoin, urlparse, parse_qs, unquote
import time
import re
from datetime import datetime

BASE_URL = "https://firestoneco.portal.civicclerk.com"
API_BASE_URL = "https://firestoneco.api.civicclerk.com/v1/"


def extract_meeting_date(page: Page, link_locator):
    """Extract meeting date from the link element
    
    Looks for date in:
    - aria-label attribute (e.g., "Board of Trustees event on Wednesday, Aug. 13, 2025 6:00 PM")
    - h2 element with date (e.g., "Aug 13, <br>2025")
    - data-date attribute on the link
    """
    try:
        # Try data-date attribute first (ISO format: "2025-08-13T18:00:00Z")
        data_date = link_locator.get_attribute("data-date")
        if data_date:
            try:
                # Parse ISO format: "2025-08-13T18:00:00Z"
                date_obj = datetime.fromisoformat(data_date.replace('Z', '+00:00'))
                return date_obj.date()
            except:
                pass
        
        # Try aria-label attribute
        aria_label = link_locator.get_attribute("aria-label")
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
            date_div = link_locator.locator("div[data-testid='dateDetails']")
            h2 = date_div.locator("h2.MuiTypography-h5")
            date_text = h2.text_content()
            if date_text:
                date_text = date_text.strip()
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


def get_js_source(page: Page):
    """Fetch and analyze the JavaScript source code"""
    try:
        # Get all script tags
        scripts = page.evaluate("""
            () => {
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
            }
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


def extract_react_data(page: Page):
    """Extract data from React component state using React DevTools"""
    try:
        # Try to access React DevTools API
        react_data = page.evaluate("""
            () => {
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
            }
        """)
        return react_data
    except Exception as e:
        print(f"  ⚠️  Could not extract React data: {e}")
        return None


def inspect_button_handlers(page: Page, element_handle):
    """Inspect JavaScript event handlers on an element
    
    This function extracts React fiber data from DOM elements, which is crucial
    for finding the remoteFile data needed to build download URLs.
    """
    try:
        handlers = page.evaluate("""
            (element) => {
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
            }
        """, element_handle)
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


class FirestoneScraper(Scraper):
    """Firestone-specific scraper implementation using Playwright"""
    
    def __init__(self):
        """Initialize Firestone scraper"""
        super().__init__(BASE_URL)
    
    def scrape_meetings(self):
        """Scrape list of meetings from Firestone portal"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = self.get_browser_context(browser, headless=True)
            page = context.new_page()
            
            try:
                page.goto(self.base_url, wait_until="networkidle")
                
                # Wait for React app to load - wait for the root div to have content
                # Wait for the event list table to appear (React needs time to render)
                page.wait_for_selector("#event-list-table", timeout=30000)
                print("✅ Found event-list-table element")
                
                # Find the ul with id="Event-list" within the div
                page.wait_for_selector("#Event-list", timeout=30000)
                print(f"✅ Found Event-list ul element")
                
                # Wait for at least one meeting item to appear (ensures React has rendered content)
                page.wait_for_selector("li.MuiListItem-container a[href]", timeout=30000)
                
                # Get all li elements within the ul and filter to only those with anchor tags
                # This skips listSubheader li elements (like "Past Events")
                event_list_ul = page.locator("#Event-list")
                all_li = event_list_ul.locator("li.MuiListItem-container")
                li_count = all_li.count()
                
                # Filter to only those with anchor tags
                li_elements = []
                for i in range(li_count):
                    li = all_li.nth(i)
                    if li.locator("a[href]").count() > 0:
                        li_elements.append(li)
                
                print(f"✅ Found {len(li_elements)} meeting items (filtered from {li_count} total li elements)")
                
                meetings = []
                for i, li in enumerate(li_elements):
                    try:
                        # Find the anchor tag within the li
                        link = li.locator("a[href]").first
                        if link.count() == 0:
                            continue
                        
                        # Extract href
                        href = link.get_attribute("href")
                        if not href:
                            continue
                        
                        # Extract data-id (event ID)
                        event_id = link.get_attribute("data-id")
                        
                        # Extract title from the h3 element with id like "eventListRow-{id}-title"
                        title = ""
                        try:
                            title_element = link.locator("h3[id^='eventListRow-'][id$='-title']")
                            if title_element.count() > 0:
                                title = title_element.text_content().strip()
                        except:
                            # Fallback: try to get text from the link itself
                            title = link.text_content().strip() if link.text_content() else ""
                        
                        # Extract meeting date
                        meeting_date = extract_meeting_date(page, link)
                        
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
                
                # Try to get page info
                try:
                    current_url = page.url
                    print(f"   Current URL: {current_url}")
                    page_title = page.title()
                    print(f"   Page title: {page_title}")
                except Exception as debug_e:
                    print(f"   Could not get page info: {debug_e}")
                
                import traceback
                print(f"   Full traceback:")
                traceback.print_exc()
                return []
            finally:
                context.close()
                browser.close()
    
    def scrape_meeting_files(self, page: Page, meeting_url: str, event_id: str, enable_network_monitoring: bool = False):
        """Scrape all files from a meeting's /files page"""
        print(f"\n📄 Scraping files for event {event_id}...")
        
        # Navigate to the files page
        files_url = urljoin(self.base_url, f"/event/{event_id}/files")
        page.goto(files_url, wait_until="networkidle")
        
        # Wait for the files list to load
        try:
            page.wait_for_selector("#files", timeout=20000)
            page.wait_for_timeout(2000)  # Wait for React to fully render
            print("✅ Files page loaded")
        except:
            print("⚠️  Could not find files list")
            return []
        
        # Get JavaScript source info
        main_js, all_scripts = get_js_source(page)
        if main_js:
            print(f"  📜 Main JS bundle: {main_js}")
            print(f"     (You can fetch this to analyze the component structure)")
        
        # Try to extract React data
        react_data = extract_react_data(page)
        if react_data:
            print(f"  📊 React root component: {react_data.get('type', 'Unknown')}")
        
        files = []
        
        # Get main files (Agenda, Agenda Packet)
        try:
            files_list = page.locator("#files")
            file_items = files_list.locator("li.MuiListItem-container")
            file_count = file_items.count()
            
            for i in range(file_count):
                try:
                    item = file_items.nth(i)
                    
                    # Get file name
                    file_name_elem = item.locator("span.MuiListItemText-primary")
                    if file_name_elem.count() == 0:
                        continue
                    file_name = file_name_elem.text_content().strip()
                    
                    # Get download button
                    try:
                        download_btn = item.locator("button[data-testid='files']")
                        if download_btn.count() == 0:
                            # No download button, just add the file name
                            files.append({
                                "name": file_name,
                                "type": "Unknown",
                                "download_url": "N/A"
                            })
                            continue
                        
                        download_btn_id = download_btn.get_attribute("id")
                        
                        print(f"    🔍 Debug main file {file_name}: download_btn_id={download_btn_id}")
                        
                        # Get element handle for React inspection
                        download_btn_handle = download_btn.element_handle()
                        
                        # Inspect the button's handlers and data to get remoteFile
                        handlers = inspect_button_handlers(page, download_btn_handle)
                        remote_file = None
                        
                        print(f"    🔍 Debug main file {file_name}: handlers={list(handlers.keys()) if handlers else None}")
                        
                        if handlers:
                            # Check if we found remoteFile in React props
                            if handlers.get('remoteFile'):
                                remote_file = handlers['remoteFile']
                                file_id = remote_file.get('fileId')
                                file_type = remote_file.get('fileType')
                                file_name = remote_file.get('name', file_name)
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
                        page.wait_for_timeout(800)  # Wait for menu to open
                        
                        # Find the menu and extract download links
                        menu = page.locator(f"#{download_btn_id}-menu")
                        menu.wait_for(state="visible", timeout=5000)
                        menu_items = menu.locator("li[role='menuitem']")
                        menu_count = menu_items.count()
                        
                        for j in range(menu_count):
                            try:
                                menu_item = menu_items.nth(j)
                                file_type_elem = menu_item.locator("span.MuiListItemText-primary")
                                if file_type_elem.count() == 0:
                                    continue
                                file_type = file_type_elem.text_content().strip()
                                
                                # Inspect menu item to find DownloadFileButton component
                                download_elem = menu_item.locator("span[data-testid='downloadFileButton']")
                                if download_elem.count() == 0:
                                    continue
                                
                                download_elem_handle = download_elem.element_handle()
                                item_handlers = inspect_button_handlers(page, download_elem_handle)
                                
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
                                        iframe = page.locator("#pdfViewerIframe")
                                        if iframe.count() > 0:
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
                                            download_links = page.locator("a[download], a[href*='GetMeetingFileStream'], a[href*='download']")
                                            if download_links.count() > 0:
                                                download_url = download_links.first.get_attribute('href')
                                                print(f"    ✅ Found download link in DOM: {download_url[:80] if download_url else 'None'}...")
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
                                page.locator("body").click(position={"x": 0, "y": 0})
                                page.wait_for_timeout(300)
                                break  # Only get first menu item for now
                                
                            except Exception as e:
                                print(f"    ⚠️  Error processing menu item: {e}")
                                pass
                    
                    except Exception as e:
                        print(f"  ⚠️  Error extracting file: {e}")
                        continue
        except Exception as e:
            print(f"  ⚠️  Error processing main files: {e}")
        
        # Get attachments - full version with download button extraction
        try:
            # Wait for attachments list to load
            page.wait_for_selector("#AttachmentsList", timeout=20000)
            attachments_list = page.locator("#AttachmentsList")
            all_items = attachments_list.locator("li")
            items_count = all_items.count()
            
            current_section = None
            
            for i in range(items_count):
                try:
                    item = all_items.nth(i)
                    
                    # Check if this is a section header
                    section_header = item.locator(".MuiListSubheader-root span")
                    if section_header.count() > 0:
                        section_text = section_header.text_content()
                        if section_text and section_text.strip():
                            current_section = section_text.strip()
                            continue
                    
                    # Check if this is a file item (button or list item)
                    file_name_elem = item.locator("span.MuiListItemText-primary")
                    if file_name_elem.count() == 0:
                        continue
                    file_name = file_name_elem.text_content().strip()
                    
                    # Try to find download button (could be reportFiles or attachmentFiles)
                    download_btn = None
                    download_btn_type = None
                    
                    report_btn = item.locator("button[data-testid='reportFiles']")
                    if report_btn.count() > 0:
                        download_btn = report_btn
                        download_btn_type = "reportFiles"
                    else:
                        attach_btn = item.locator("button[data-testid='attachmentFiles']")
                        if attach_btn.count() > 0:
                            download_btn = attach_btn
                            download_btn_type = "attachmentFiles"
                    
                    if download_btn and download_btn.count() > 0:
                        download_btn_id = download_btn.get_attribute("id")
                        
                        print(f"    🔍 Debug attachment {file_name}: download_btn_id={download_btn_id}, type={download_btn_type}")
                        
                        # Get element handle for React inspection
                        download_btn_handle = download_btn.element_handle()
                        
                        # Inspect button to get remoteFile data
                        handlers = inspect_button_handlers(page, download_btn_handle)
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
                        page.wait_for_timeout(800)
                        
                        try:
                            # Find the menu
                            menu = page.locator(f"#{download_btn_id}-menu")
                            menu.wait_for(state="visible", timeout=5000)
                            menu_items = menu.locator("li[role='menuitem']")
                            menu_count = menu_items.count()
                            
                            # Process each menu item (PDF, Plain Text, etc.)
                            for j in range(menu_count):
                                try:
                                    menu_item = menu_items.nth(j)
                                    file_type_elem = menu_item.locator("span.MuiListItemText-primary")
                                    if file_type_elem.count() == 0:
                                        continue
                                    file_type_text = file_type_elem.text_content().strip()
                                    
                                    # Find the download button in the menu item
                                    download_elem = menu_item.locator("span[data-testid='downloadFileButton']")
                                    if download_elem.count() == 0:
                                        continue
                                    
                                    download_elem_handle = download_elem.element_handle()
                                    
                                    # Try to get remoteFile from menu item
                                    item_handlers = inspect_button_handlers(page, download_elem_handle)
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
                                        print(f"      ✅ Built download URL: {download_url[:80] if download_url else 'None'}...")
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
                            page.locator("body").click(position={"x": 0, "y": 0})
                            page.wait_for_timeout(300)
                        except Exception as e:
                            print(f"    ⚠️  Error opening menu for {file_name}: {e}")
                            # Close menu if open
                            try:
                                page.locator("body").click(position={"x": 0, "y": 0})
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
    
    def _download_files_via_clicks(self, page: Page, meeting: dict, meeting_download_dir: str):
        """Download files by clicking download buttons"""
        print(f"   📥 Clicking download buttons (files will be saved to {meeting_download_dir})...")
        
        # Navigate to files page to click buttons
        files_url = urljoin(self.base_url, f"/event/{meeting['event_id']}/files")
        page.goto(files_url, wait_until="networkidle")
        page.wait_for_timeout(3000)  # Wait for page to load
        
        # Wait for files list and attachments list
        try:
            page.wait_for_selector("#files", timeout=20000)
            page.wait_for_selector("#AttachmentsList", timeout=20000)
            page.wait_for_timeout(2000)  # Extra wait for React to render
        except:
            print(f"   ⚠️  Could not load files page")
            return
        
        # Set up download listener
        download_paths = []
        
        def handle_download(download):
            # Save to meeting-specific directory
            file_path = os.path.join(meeting_download_dir, download.suggested_filename)
            download.save_as(file_path)
            download_paths.append(file_path)
            print(f"      ✅ Download saved: {download.suggested_filename}")
        
        page.on("download", handle_download)
        
        # Find all download buttons on the page and click them
        print(f"   🔍 Finding all download buttons on page...")
        
        # Find all download buttons in main files list
        main_files_buttons = []
        try:
            files_list = page.locator("#files")
            list_items = files_list.locator("li.MuiListItem-container")
            items_count = list_items.count()
            
            for i in range(items_count):
                try:
                    item = list_items.nth(i)
                    file_name_elem = item.locator("span.MuiListItemText-primary")
                    if file_name_elem.count() == 0:
                        continue
                    file_name = file_name_elem.text_content().strip()
                    download_btn = item.locator("button[data-testid='files']")
                    if download_btn.count() > 0:
                        main_files_buttons.append((file_name, download_btn))
                except:
                    continue
        except:
            pass
        
        # Find all download buttons in attachments list
        attachment_buttons = []
        try:
            attachments_list = page.locator("#AttachmentsList")
            all_items = attachments_list.locator("li")
            items_count = all_items.count()
            
            for i in range(items_count):
                try:
                    item = all_items.nth(i)
                    # Skip section headers
                    if item.locator(".MuiListSubheader-root").count() > 0:
                        continue
                    
                    # Skip "No Attachment File" items
                    name_elems = item.locator("span.MuiListItemText-primary")
                    if name_elems.count() == 0:
                        continue
                    file_name = name_elems.text_content().strip()
                    
                    if 'No Attachment File' in file_name:
                        continue
                    
                    # Try to find download button (either attachmentFiles or reportFiles)
                    download_btn = None
                    for btn_type in ['attachmentFiles', 'reportFiles']:
                        btn = item.locator(f"button[data-testid='{btn_type}']")
                        if btn.count() > 0:
                            download_btn = btn
                            break
                    
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
                download_btn.scroll_into_view_if_needed()
                page.wait_for_timeout(500)
                
                # Click the download button to open menu
                download_btn.click()
                page.wait_for_timeout(1500)  # Wait for menu to appear
                
                # Find the menu (it should have an ID based on the button ID)
                download_btn_id = download_btn.get_attribute("id")
                if download_btn_id:
                    menu = page.locator(f"#{download_btn_id}-menu")
                    menu.wait_for(state="visible", timeout=5000)
                    menu_items = menu.locator("li[role='menuitem']")
                    
                    if menu_items.count() > 0:
                        # Click the first menu item (usually PDF)
                        menu_item = menu_items.first
                        download_span = menu_item.locator("span[data-testid='downloadFileButton']")
                        if download_span.count() > 0:
                            print(f"      ✅ Clicking download in menu...")
                            download_span.click()
                            page.wait_for_timeout(3000)  # Wait for download to start
                            print(f"      ✅ Download started")
                    else:
                        print(f"      ⚠️  No menu items found")
                    
                    # Close menu
                    try:
                        page.locator("body").click(position={"x": 0, "y": 0})
                        page.wait_for_timeout(500)
                    except:
                        pass
                else:
                    print(f"      ⚠️  Button has no ID")
            except Exception as e:
                print(f"      ⚠️  Error: {e}")
                # Close menu if it opened
                try:
                    page.locator("body").click(position={"x": 0, "y": 0})
                    page.wait_for_timeout(500)
                except:
                    pass


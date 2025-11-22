"""Abstract base class for meeting scrapers using Playwright"""
from abc import ABC, abstractmethod
from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
from datetime import date
import os
import requests
import re


class Scraper(ABC):
    """Abstract base class for meeting scrapers using Playwright"""
    
    def __init__(self, base_url: str):
        """Initialize scraper with base URL
        
        Args:
            base_url: Base URL for the portal
        """
        self.base_url = base_url
    
    @abstractmethod
    def scrape_meetings(self):
        """Scrape list of meetings from the portal
        
        Returns:
            List of meeting dicts with keys: event_id, title, url, href, date
        """
        pass
    
    @abstractmethod
    def scrape_meeting_files(self, page: Page, meeting_url: str, event_id: str, enable_network_monitoring: bool = False):
        """Scrape all files from a meeting's files page
        
        Args:
            page: Playwright Page instance
            meeting_url: URL of the meeting
            event_id: Event/meeting ID
            enable_network_monitoring: Whether to enable network monitoring
            
        Returns:
            List of file dicts with download URLs and metadata
        """
        pass
    
    def get_browser_context(self, browser: Browser, headless: bool = True, download_dir: str = None) -> BrowserContext:
        """Get browser context with anonymization settings
        
        Args:
            browser: Playwright Browser instance
            headless: Whether to run in headless mode
            download_dir: Directory for downloads (if None, uses default)
            
        Returns:
            BrowserContext instance
        """
        context_options = {
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "locale": "en-US",
            "timezone_id": "America/Denver",
        }
        
        # Set up download directory if provided
        if download_dir:
            context_options["accept_downloads"] = True
        
        context = browser.new_context(**context_options)
        
        # Remove webdriver property to avoid detection
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        return context
    
    def download_file(self, url: str, filepath: str) -> bool:
        """Download a file from URL to filepath"""
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Create directory if it doesn't exist
            dir_path = os.path.dirname(filepath)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            # Write file
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return True
        except Exception as e:
            print(f"    ❌ Error downloading {filepath}: {e}")
            return False
    
    def filter_meetings_by_date_range(self, meetings, start_date=None, end_date=None):
        """Filter meetings by date range
        
        Args:
            meetings: List of meeting dicts
            start_date: date object for start of range (inclusive)
            end_date: date object for end of range (inclusive)
        
        Returns:
            Filtered list of meetings
        """
        if not start_date and not end_date:
            return meetings
        
        filtered = []
        for meeting in meetings:
            meeting_date = meeting.get('date')
            if not meeting_date:
                continue
            
            # Check if date is in range
            if start_date and meeting_date < start_date:
                continue
            if end_date and meeting_date > end_date:
                continue
            
            filtered.append(meeting)
        
        return filtered
    
    def scrape_meetings_with_files(self, download_files=False, download_dir="./downloads", 
                                     max_meetings=None, start_date=None, end_date=None, 
                                     use_click_download=False):
        """Scrape meetings and their associated files
        
        Args:
            download_files: If True, download files to download_dir
            download_dir: Directory to save downloaded files
            max_meetings: Maximum number of meetings to process (None = all). Takes most recent (bottom of list).
            start_date: date object for start of date range (inclusive)
            end_date: date object for end of date range (inclusive)
            use_click_download: If True, use Playwright click downloads instead of URL downloads
            
        Returns:
            List of meeting dicts with files attached
        """
        # First, get all meetings
        try:
            meetings = self.scrape_meetings()
        except Exception as e:
            print(f"❌ Error getting meetings list: {e}")
            print(f"   Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            return []
        
        if not meetings:
            print("❌ No meetings found")
            print("   Possible reasons:")
            print("   - Website structure changed")
            print("   - Date range filtered out all meetings")
            print("   - React app didn't load properly")
            return []
        
        # Filter by date range if specified
        total_meetings = len(meetings)
        if start_date or end_date:
            meetings = self.filter_meetings_by_date_range(meetings, start_date, end_date)
            if len(meetings) == 0:
                print(f"\n❌ No meetings found in date range (from {total_meetings} total)")
                if start_date:
                    print(f"   Start date: {start_date.strftime('%Y-%m-%d')}")
                if end_date:
                    print(f"   End date: {end_date.strftime('%Y-%m-%d')}")
                return []
            print(f"\n📅 Filtered to {len(meetings)} meeting(s) in date range (from {total_meetings} total)")
            if start_date:
                print(f"   Start date: {start_date.strftime('%Y-%m-%d')}")
            if end_date:
                print(f"   End date: {end_date.strftime('%Y-%m-%d')}")
        
        # Limit to most recent N meetings if specified
        if max_meetings is not None and max_meetings > 0:
            if len(meetings) == 0:
                print(f"\n❌ No meetings to process")
                return []
            # Get the last N meetings (most recent = bottom of list)
            meetings = meetings[-max_meetings:]
            print(f"\n📊 Processing {len(meetings)} most recent meeting(s)")
        
        # Launch Playwright browser
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            
            # Create context with download directory if needed
            context = self.get_browser_context(
                browser, 
                headless=True, 
                download_dir=download_dir if (download_files and use_click_download) else None
            )
            
            # Set up download handling if using click downloads
            if download_files and use_click_download:
                # Downloads will be handled by the page's download event listener
                pass
            
            page = context.new_page()
            
            try:
                for meeting in meetings:
                    try:
                        files = self.scrape_meeting_files(
                            page, 
                            meeting['url'], 
                            meeting['event_id'], 
                            enable_network_monitoring=use_click_download
                        )
                        meeting['files'] = files
                        
                        print(f"\n📋 Meeting: {meeting['title']}")
                        print(f"   Files found: {len(files)}")
                    except Exception as e:
                        print(f"\n❌ Error scraping files for meeting {meeting.get('event_id', 'unknown')}: {e}")
                        print(f"   Error type: {type(e).__name__}")
                        meeting['files'] = []
                        continue
                    
                    # Download files if flag is set
                    if download_files:
                        meeting_download_dir = os.path.join(download_dir, f"event_{meeting['event_id']}")
                        os.makedirs(meeting_download_dir, exist_ok=True)
                        
                        if use_click_download:
                            # Use Playwright to click download buttons (implemented in subclass)
                            self._download_files_via_clicks(page, meeting, meeting_download_dir)
                        else:
                            # Use URL-based download
                            for f in files:
                                file_name = f.get('name', 'Unknown')
                                url = f.get('download_url')
                                if url and url != "N/A":
                                    # Determine file extension
                                    if f.get('plain_text'):
                                        ext = '.txt'
                                    elif f.get('type', '').lower().endswith('pdf'):
                                        ext = '.pdf'
                                    else:
                                        ext = '.pdf'  # default
                                    
                                    # Sanitize filename
                                    safe_name = re.sub(r'[^\w\s-]', '', file_name).strip()
                                    safe_name = re.sub(r'[-\s]+', '-', safe_name)
                                    filename = f"{safe_name}{ext}"
                                    filepath = os.path.join(meeting_download_dir, filename)
                                    
                                    print(f"   📥 Downloading: {filename}")
                                    if self.download_file(url, filepath):
                                        file_size = os.path.getsize(filepath)
                                        print(f"      ✅ Downloaded ({file_size:,} bytes)")
                                    else:
                                        print(f"      ❌ Failed to download")
                                else:
                                    print(f"   ⚠️  Skipping {file_name} (no URL available)")
                    else:
                        # Just print file info
                        for f in files[:5]:  # Show first 5
                            print(f"   - {f.get('name', 'Unknown')} ({f.get('type', 'Unknown type')})")
                        if len(files) > 5:
                            print(f"   ... and {len(files) - 5} more")
            
            except Exception as e:
                print(f"\n❌ Error in scrape_meetings_with_files: {e}")
                print(f"   Error type: {type(e).__name__}")
                import traceback
                traceback.print_exc()
                return [] if meetings is None else meetings
            finally:
                context.close()
                browser.close()
        
        return meetings if meetings is not None else []
    
    def _download_files_via_clicks(self, page: Page, meeting: dict, meeting_download_dir: str):
        """Download files by clicking download buttons (to be overridden by subclasses)
        
        Args:
            page: Playwright Page instance
            meeting: Meeting dict with event_id
            meeting_download_dir: Directory to save downloaded files
        """
        raise NotImplementedError("Subclasses must implement _download_files_via_clicks")


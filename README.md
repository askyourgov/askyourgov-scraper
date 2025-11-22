# About AskYourGov

AskYourGov is an independent, citizen-powered transparency initiative dedicated to making public information actually *public*. Local governments, HOAs, special districts, school boards, and municipalities generate mountains of documents—budgets, agendas, contracts, emails, audits, ALPR deployments, and more. Most of it is technically “public” but practically unreachable, scattered across outdated portals, PDFs, and paywalled systems.

AskYourGov aims to fix that.

## Our Mission
- **Collect** every publicly accessible record or dataset  
- **Standardize** it into structured, searchable data  
- **Analyze** it with modern AI tooling  
- **Expose** it in a public, citizen-friendly interface  

This gives communities a real view into how decisions are made, how money is spent, and how power is exercised—without requiring legal expertise or hours of digging.

AskYourGov is not affiliated with any government agency. We exist for one purpose: **watch the watchers.**

---

# About This Repo — `askyourgov-scraper`

This repository houses the **core ingestion engine** of the AskYourGov platform.

It is the system responsible for collecting raw data from the real world.

## What It Does
- Automated **Playwright spiders** to crawl municipal websites, agenda portals, HOA management systems, and state data dashboards  
- **CORA/FOIA workflow automation** to track, download, organize, and ingest public-records responses  
- **Meeting scraping** for agendas, minutes, audio/video transcripts, resolutions, and attachments  
- **PDF ingestion & OCR** for scanned documents, contracts, budgets, and image-only files  
- **Queue-driven job orchestration** to ensure reliability, retries, backoff logic, and fault-tolerance  
- Output of **clean, structured JSON** ready for indexing and AI extraction  

## Why It Matters
This repo is the **workhorse** of the entire AskYourGov ecosystem.  
Without high-reliability scraping and ingestion, the rest of the platform has nothing to analyze or expose. This system ensures every public document—no matter where it’s buried—gets captured, normalized, and made searchable.


# Firestone Meeting Scraper

A Python scraper for extracting meeting data and files from the Firestone Town CivicClerk portal. This project provides two browser automation implementations (Selenium and Playwright) to scrape meeting information and associated documents.

## Overview

The Firestone Town portal uses a React-based application that presents unique challenges for web scraping. This project includes two complete implementations:

- **Selenium-based scraper** (`selenium_meeting_scraper/`) - Uses Selenium WebDriver with Chrome
- **Playwright-based scraper** (`playwright_meeting_scraper/`) - Uses Playwright with Chromium

Both implementations handle the React DOM quirks and extract meeting data, file metadata, and download URLs.

## Features

- ✅ Scrape meeting lists with dates, titles, and event IDs
- ✅ Extract file metadata (Agenda, Agenda Packet, Attachments)
- ✅ Build download URLs from React component state
- ✅ Download files via URL or click-based methods
- ✅ Filter meetings by date range
- ✅ Limit processing to most recent N meetings
- ✅ Handle React Fiber tree inspection to extract file data
- ✅ Support for Azure Blob Storage direct URLs and API URLs

## Installation

### Prerequisites

- Python 3.12+
- Chrome/Chromium browser
- For Playwright: Browser binaries (installed automatically)

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Install Playwright Browsers (if using Playwright backend)

```bash
playwright install chromium
```

## Usage

### Basic Usage

The unified CLI supports both backends via the `--backend` flag:

```bash
# Use Selenium (default)
python scraper_cli.py

# Use Playwright
python scraper_cli.py --backend playwright
```

### Examples

```bash
# Just list meetings and files (no download)
python scraper_cli.py

# Download all files using Selenium
python scraper_cli.py --download

# Download files using Playwright backend
python scraper_cli.py --backend playwright --download

# Download to custom directory
python scraper_cli.py -d --download-dir ./my_downloads

# Just list meetings (no files)
python scraper_cli.py --meetings-only

# Process only the 2 most recent meetings
python scraper_cli.py --meeting-count 2

# Download files from 2 most recent meetings
python scraper_cli.py --meeting-count 2 -d

# Show meetings in October 2025
python scraper_cli.py --start 2025-10-01 --end 2025-10-31

# Download files from meetings in date range
python scraper_cli.py --start 2025-10-01 --end 2025-10-31 -d --backend playwright

# Use click-based downloads (recommended if URL downloads fail)
python scraper_cli.py --click-download --download
```

### CLI Arguments

- `--backend {selenium,playwright}` - Choose browser automation backend (default: selenium)
- `-d, --download` - Download files instead of just printing URLs
- `--download-dir DIR` - Directory to save downloaded files (default: ./downloads)
- `--meetings-only` - Only scrape meeting list, not files
- `--meeting-count N` - Maximum number of meetings to process (takes most recent N)
- `--start YYYY-MM-DD` - Start date for date range filtering (inclusive)
- `--end YYYY-MM-DD` - End date for date range filtering (inclusive)
- `--click-download` - Use click-based downloads instead of URL downloads

## Project Structure

```
firestone_scraper/
├── selenium_meeting_scraper/      # Selenium-based implementation
│   ├── __init__.py
│   ├── base.py                    # Abstract base class
│   └── firestone.py               # Firestone-specific scraper
├── playwright_meeting_scraper/    # Playwright-based implementation
│   ├── __init__.py
│   ├── base.py                    # Abstract base class
│   └── firestone.py               # Firestone-specific scraper
├── scraper_cli.py                 # Unified CLI entry point
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## Output Structure

When files are downloaded, they are organized by meeting event in the `downloads/` directory (or your specified `--download-dir`). Each meeting gets its own folder named `event_{event_id}_{date}_{meeting_title}`.

### Example Directory Structure

```
downloads/
├── event_1181_03-12-2025_Board_of_Trustees_Meeting/
│   ├── 03-12-2025 Board of Trustees Meeting Agenda Packet.pdf
│   ├── 03-12-2025 Board of Trustees Meeting Agenda.pdf
│   ├── March 12 2025 Board of Trustees Meeting Minutes.pdf
│   ├── Board of Trustees Meeting.mp4
│   ├── closed_captions.srt
│   └── transcription.pdf
├── event_1064_02-06-2025_Planning_and_Zoning_Commission_Meeting/
│   ├── 02-06-2025 Planning and Zoning Commission Meeting Agenda Packet.pdf
│   ├── 02-06-2025 Planning and Zoning Commission Meeting Agenda.pdf
│   └── Planning & Zoning Commission Meeting.mp4
└── event_1034_01-08-2025_Board_of_Trustees_Meeting/
    ├── 01-08-2025 Board of Trustees Meeting Agenda Packet.pdf
    ├── 01-08-2025 Board of Trustees Meeting Agenda.pdf
    ├── January  8 2025 Board of Trustees Meeting Minutes.pdf
    ├── Board of Trustees Meeting.mp4
    ├── closed_captions.srt
    └── transcription.pdf
```

### File Types Downloaded

The scraper downloads various file types depending on what's available for each meeting:

- **PDF Documents:**
  - Agenda files (e.g., `03-12-2025 Board of Trustees Meeting Agenda.pdf`)
  - Agenda Packets (e.g., `03-12-2025 Board of Trustees Meeting Agenda Packet.pdf`)
  - Meeting Minutes (e.g., `March 12 2025 Board of Trustees Meeting Minutes.pdf`)
  - Other attachments and reports

- **Media Files:**
  - Video recordings (`.mp4` files)
  - Audio recordings (if available)

- **Transcripts & Captions:**
  - Closed captions (`.srt` subtitle files)
  - Text transcriptions (`.pdf` or `.txt` files)

### Additional Output Directories

- **`docs/`** - May contain processed documents, OCR'd PDFs, or other documentation files (not automatically generated by the scraper)

## React DOM Challenges

The Firestone portal uses a React-based single-page application (SPA) that presents several challenges for web scraping:

### 1. Dynamic Content Loading
- Content is rendered client-side via React
- Elements may not exist immediately after page load
- Requires waiting for React to finish rendering

### 2. React Fiber Tree Inspection
The scraper extracts file metadata by inspecting React's internal Fiber tree:

```javascript
// Finding React fiber nodes
function findReactFiber(element) {
    for (let key in element) {
        if (key.startsWith('__reactInternalInstance') || key.startsWith('__reactFiber')) {
            return element[key];
        }
    }
    return null;
}
```

### 3. Component State Extraction
File download URLs are stored in React component props (`remoteFile`), not in the DOM:

- Files have a `remoteFile` object with `fileId`, `fileType`, `streamUrl`, etc.
- The scraper walks up the React Fiber tree to find `DownloadFileButton` components
- Extracts `memoizedProps` and `pendingProps` to get file metadata

### 4. Menu Interactions
- Download buttons open Material-UI menus dynamically
- Menu items contain nested React components
- Must inspect menu item components to get file-specific data

### 5. Multiple Download URL Sources
The scraper handles multiple URL sources:
- **Direct Azure Blob Storage URLs** (`streamUrl` with SAS tokens) - preferred
- **API URLs** - constructed from `fileId` and file type
- **Fallback methods** - iframe inspection, DOM link extraction

### 6. React-Specific Selectors
- Uses React DevTools-style selectors (`__reactFiber*`, `__reactInternalInstance*`)
- Waits for React-specific elements (`data-testid` attributes)
- Handles Material-UI component structure

## Backend Comparison

### Selenium (`selenium_meeting_scraper`)
- **Pros:**
  - Mature, widely-used library
  - Good documentation and community support
  - Works with existing Chrome installations
  
- **Cons:**
  - Requires ChromeDriver management
  - Slightly slower than Playwright
  - More verbose API

### Playwright (`playwright_meeting_scraper`)
- **Pros:**
  - Faster execution
  - Better built-in waiting mechanisms
  - More modern API
  - Built-in download handling
  
- **Cons:**
  - Requires browser binary installation
  - Newer library (less community resources)
  - Slightly larger dependency footprint

**Recommendation:** Both implementations work well. Use Playwright if you want better performance and modern features. Use Selenium if you prefer a more established library.

## Troubleshooting

### "No meetings found"
- The React app may not have loaded properly
- Website structure may have changed
- Check browser console for JavaScript errors
- Try increasing wait times in the code

### "Could not extract download URL"
- React component structure may have changed
- File may not have a `remoteFile` prop
- Try using `--click-download` flag instead

### Download failures
- Check network connectivity
- Verify file URLs are accessible
- Try `--click-download` for click-based downloads
- Check if Azure Blob Storage URLs have expired (SAS tokens)

### Browser detection issues
- Both implementations include anti-detection measures
- If blocked, try adjusting user agent or headless settings
- Consider adding delays between requests

## Development

### Adding a New Scraper

To add support for another portal:

1. Create a new scraper class inheriting from `Scraper` base class
2. Implement `scrape_meetings()` and `scrape_meeting_files()` methods
3. Implement `_download_files_via_clicks()` if using click downloads
4. Add to the appropriate package (`selenium_meeting_scraper` or `playwright_meeting_scraper`)

### Testing

```bash
# Test Selenium implementation
python scraper_cli.py --meetings-only --backend selenium

# Test Playwright implementation  
python scraper_cli.py --meetings-only --backend playwright
```

## Dependencies

- `selenium>=4.25.0` - Selenium WebDriver
- `webdriver-manager>=4.0.2` - ChromeDriver management
- `playwright>=1.40.0` - Playwright browser automation
- `requests>=2.31.0` - HTTP library for file downloads

## License
GNU Affero General Public License v3.0 (AGPL-3.0)
https://www.gnu.org/licenses/agpl-3.0.en.html

## Contributing

Post a PR!

## Notes

- The scraper respects the website's structure and extracts publicly available data
- Files are downloaded to `./downloads/` by default, organized by event ID
- The scraper includes error handling and will continue processing even if individual files fail
- Both implementations use headless browsers by default for efficiency


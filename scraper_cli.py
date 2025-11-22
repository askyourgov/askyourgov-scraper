"""CLI entry point for meeting scrapers"""
import argparse
from datetime import datetime


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Scrape Firestone Town meetings and their files from CivicClerk portal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Just list meetings and files (no download)
  python scraper_cli.py
  
  # Download all files
  python scraper_cli.py --download
  
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
  
  # Show 2 most recent meetings in October 2025
  python scraper_cli.py --meeting-count 2 --start 2025-10-01 --end 2025-10-31
  
  # Download files from meetings in date range
  python scraper_cli.py --start 2025-10-01 --end 2025-10-31 -d
  
  # Use Playwright backend instead of Selenium (default)
  python scraper_cli.py --backend playwright --download
        """
    )
    
    parser.add_argument(
        '--backend',
        type=str,
        choices=['selenium', 'playwright'],
        default='selenium',
        help='Browser automation backend to use (default: selenium)'
    )
    
    parser.add_argument(
        '-d', '--download',
        action='store_true',
        help='Download files instead of just printing URLs'
    )
    
    parser.add_argument(
        '--download-dir',
        type=str,
        default='./downloads',
        help='Directory to save downloaded files (default: ./downloads)'
    )
    
    parser.add_argument(
        '--meetings-only',
        action='store_true',
        help='Only scrape meeting list, not files'
    )
    
    parser.add_argument(
        '--meeting-count',
        type=int,
        default=None,
        metavar='N',
        help='Maximum number of meetings to process (default: all). Takes most recent N meetings.'
    )
    
    parser.add_argument(
        '--start',
        type=str,
        default=None,
        metavar='YYYY-MM-DD',
        help='Start date for date range filtering (format: YYYY-MM-DD, inclusive)'
    )
    
    parser.add_argument(
        '--end',
        type=str,
        default=None,
        metavar='YYYY-MM-DD',
        help='End date for date range filtering (format: YYYY-MM-DD, inclusive)'
    )
    
    parser.add_argument(
        '--click-download',
        action='store_true',
        help='Use click downloads instead of URL downloads (recommended if URLs fail)'
    )
    
    args = parser.parse_args()
    
    # Import the appropriate scraper based on backend choice
    if args.backend == 'playwright':
        from playwright_meeting_scraper import FirestoneScraper
    else:
        from selenium_meeting_scraper import FirestoneScraper
    
    # Parse date arguments
    start_date = None
    end_date = None
    
    if args.start:
        try:
            start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
        except ValueError:
            print(f"❌ Error: Invalid start date format '{args.start}'. Use YYYY-MM-DD format.")
            return
    
    if args.end:
        try:
            end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
        except ValueError:
            print(f"❌ Error: Invalid end date format '{args.end}'. Use YYYY-MM-DD format.")
            return
    
    if start_date and end_date and start_date > end_date:
        print(f"❌ Error: Start date ({start_date}) must be before or equal to end date ({end_date})")
        return
    
    # Create scraper instance
    scraper = FirestoneScraper()
    
    if args.meetings_only:
        # Just scrape meeting list
        meetings = scraper.scrape_meetings()
        
        # Filter by date range if specified
        if start_date or end_date:
            meetings = scraper.filter_meetings_by_date_range(meetings, start_date, end_date)
            print(f"\n📅 Filtered to {len(meetings)} meeting(s) in date range")
        
        # Limit to most recent N meetings if specified
        if args.meeting_count is not None and args.meeting_count > 0:
            meetings = meetings[-args.meeting_count:]
            print(f"\n📊 Showing {len(meetings)} most recent meeting(s)")
        
        print(f"\n✅ Scraped {len(meetings)} meetings")
    else:
        # Scrape meetings and their files
        meetings = scraper.scrape_meetings_with_files(
            download_files=args.download,
            download_dir=args.download_dir,
            max_meetings=args.meeting_count,
            start_date=start_date,
            end_date=end_date,
            use_click_download=args.click_download
        )
        
        # Guard rail: Check if meetings is None or empty
        if meetings is None:
            print("\n❌ Error: scrape_meetings_with_files returned None")
            print("   This indicates an unexpected error occurred during scraping")
            return
        elif len(meetings) == 0:
            print("\n⚠️  No meetings found to process")
            print("   Possible reasons:")
            print("   - Date range filtered out all meetings")
            print("   - Website structure changed")
            print("   - React app didn't load properly")
            return
        
        if args.download:
            print(f"\n✅ Scraped {len(meetings)} meeting(s) and downloaded files to {args.download_dir}")
        else:
            print(f"\n✅ Scraped {len(meetings)} meeting(s) and extracted file URLs")
            print(f"   Use --download flag to download files")


if __name__ == "__main__":
    main()

"""Selenium-based meeting scrapers package"""
from .base import Scraper
from .firestone import FirestoneScraper

__all__ = ['Scraper', 'FirestoneScraper']
__version__ = '1.0.0'


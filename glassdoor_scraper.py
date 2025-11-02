#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Modern Glassdoor Job Scraper
Works on Linux (Ubuntu) with Selenium and Chromium
Handles login wall with manual intervention
"""

import os
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

def wait_for_user_ready(driver, timeout=180):
    """Wait for user to manually handle login and indicate they're ready."""
    print("\n" + "="*70)
    print("⏸️  MANUAL INTERVENTION REQUIRED")
    print("="*70)
    print("1. If you see a login/signup page, please LOG IN manually")
    print("2. After login, make sure you can see the JOB LISTINGS")
    print("3. Once you can see jobs, PRESS ENTER in this terminal to continue")
    print("="*70)
    
    input("\n👉 Press ENTER when you can see job listings in the browser... ")
    print("\n✅ Continuing with scraping...\n")
    time.sleep(2)

def safe_find(base_element, selectors_list, default="-1"):
    """Try multiple selectors within a base element and return first match."""
    if isinstance(selectors_list, str):
        selectors_list = [selectors_list]
    
    for selector in selectors_list:
        try:
            if selector.startswith(("//", ".//")): # Check if it's an XPath
                element = base_element.find_element(By.XPATH, selector)
            else:
                element = base_element.find_element(By.CSS_SELECTOR, selector)
            text = element.text.strip()
            if text:
                return text
        except:
            continue
    return default

def close_any_modal(driver):
    """Try to find and close any modal popups."""
    try:
        close_selectors = [
            "button[data-test='close-modal']",
            "button[aria-label='Close']",
            "button.CloseButton",
            "svg[data-test='close-icon']",
            "span[aria-label='Close']" # A new one I've seen
        ]
        for selector in close_selectors:
            try:
                close_btn = driver.find_element(By.CSS_SELECTOR, selector)
                close_btn.click()
                time.sleep(1) # Give it a second to close
                return # Stop after closing one
            except:
                pass # Selector not found, try next
    except Exception as e:
        pass # No modal found or error, just continue

def get_jobs(keyword: str, num_jobs: int, headless: bool = False, verbose: bool = True):
    """Scrape Glassdoor job data for a given keyword and location."""

    if headless:
        print("⚠️  Warning: Headless mode disabled for Glassdoor (login required)")
        headless = False

    options = Options()
    
    # Add your persistent profile
    try:        
        profile_path = os.path.join(os.getcwd(), "chrome_profile")
        options.add_argument(f"--user-data-dir={profile_path}")
    except Exception as e:
        print(f"ERROR: Could not set user-data-dir. Check your path: {e}")
        print("Continuing without a profile. You will need to log in.")

    # All your other options
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    try:
        options.binary_location = "/usr/bin/chromium-browser"
    except:
        pass
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        print(f"Error initializing Chrome: {e}")
        driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": 'Mozilla/5.Example/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    search_url = (
        f'https://www.glassdoor.com/Job/jobs.htm?sc.keyword={keyword}'
        f"&locT=&locId=jobType="
    )
    
    print(f"🌐 Navigating to: {search_url}\n")
    driver.get(search_url)

    print("✅ Browser is using your saved profile. Should be logged in.")
    print("   Pausing 5 seconds to let page load fully...")
    time.sleep(3) # Give the page 5s to load with you logged in
    
    close_any_modal(driver) 

    jobs = []
    page_num = 1
    max_pages = 10  # Safety limit for *page loads*, not scrolls
    
    # --- START OF NEW LOGIC ---
    # This counter tracks how many cards we've processed on the *current page*
    scraped_card_count = 0
    # --- END OF NEW LOGIC ---

    while len(jobs) < num_jobs and page_num <= max_pages:
        if verbose:
            print(f"\n📄 Scanning page {page_num}...")
        
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "li[data-test='jobListing'], li.JobsList_jobListItem__wjThv, div[data-test='job-listing']"))
            )
        except TimeoutException:
            print("⚠️  Could not find job listings on this page. Stopping.")
            break

        # Get ALL job cards currently on the page
        all_job_cards = driver.find_elements(By.CSS_SELECTOR, "li[data-test='jobListing']")
        if not all_job_cards:
             all_job_cards = driver.find_elements(By.CSS_SELECTOR, "li.JobsList_jobListItem__wjThv, div[data-test='job-listing']")

        # --- START OF MODIFIED LOGIC ---
        # Slice the list to get only the *new* cards
        new_job_cards = all_job_cards[scraped_card_count:]
        
        if verbose:
            print(f"   ✓ Found {len(all_job_cards)} total cards, {len(new_job_cards)} are new.")
        
        # If "Show more" was clicked but no new cards loaded, we're done
        if not new_job_cards and scraped_card_count > 0:
            print("   - 'Show more' clicked but no new jobs loaded. Checking for navigation...")
        # --- END OF MODIFIED LOGIC ---
            
        if not all_job_cards:
            print("⚠️  No job cards found on this page.")
            break
            
        # Loop over *only the new cards*
        for idx, card in enumerate(new_job_cards):
            if len(jobs) >= num_jobs:
                break
            
            close_any_modal(driver)

            try:
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", card)
                time.sleep(0.4)
                try:
                    card.click()
                except:
                    driver.execute_script("arguments[0].click();", card)
                
                time.sleep(2) 
            except Exception as e:
                if verbose:
                    print(f"   ⚠️  Could not click card {idx+1} (new card index): {str(e)[:50]}")
                continue

            try:
                detail_pane = WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-test='job-details-panel'], div[class*='JobDetails_jobDetails']"))
                )
            except TimeoutException:
                if verbose:
                    print(f"   ⚠️  Could not find detail pane for card {idx+1}. Skipping.")
                continue
            
            # --- Extract data (all your correct selectors) ---
            job_title = safe_find(detail_pane, ["h1.heading_Level1__w42c9", "h1[id*='jd-job-title-']", "div[data-test='jobTitle']"])
            company_name = safe_find(detail_pane, ["div.EmployerProfile_employerNameHeading__bXBYr", "div[data-test='employerName']"])
            rating = safe_find(detail_pane, ["span.rating-single-star_RatingText__5fdjN", "span[data-test='detailRating']"])
            location = safe_find(detail_pane, ["div[data-test='location']"])
            salary_estimate = safe_find(detail_pane, ["div[data-test='detailSalary']", "span[data-test='detailSalary']"])
            job_description = safe_find(detail_pane, ["div.JobDetails_jobDescription__uW_fK", "div[data-test='jobDescriptionText']"])
            headquarters = safe_find(detail_pane, [".//div[span[text()='Headquarters']]/div"])
            size = safe_find(detail_pane, [".//div[span[text()='Size']]/div"])
            founded = safe_find(detail_pane, [".//div[span[text()='Founded']]/div"])
            type_of_ownership = safe_find(detail_pane, [".//div[span[text()='Type']]/div"])
            industry = safe_find(detail_pane, [".//div[span[text()='Industry']]/div"])
            sector = safe_find(detail_pane, [".//div[span[text()='Sector']]/div"])
            revenue = safe_find(detail_pane, [".//div[span[text()='Revenue']]/div"])
            competitors = safe_find(detail_pane, [".//div[span[text()='Competitors']]/div"])

            job_data = {
                "Job Title": job_title, "Company": company_name, "Location": location,
                "Salary Estimate": salary_estimate, "Rating": rating,
                "Description": job_description[:500] + "..." if len(job_description) > 500 else job_description,
                "Headquarters": headquarters, "Size": size, "Founded": founded,
                "Ownership": type_of_ownership, "Industry": industry, "Sector": sector,
                "Revenue": revenue, "Competitors": competitors,
            }
            
            jobs.append(job_data)
            if verbose:
                print(f"   ✓ [{len(jobs)}/{num_jobs}] {job_title[:40]}... @ {company_name[:30]}...")

        jobs.to_csv("glassdoor_jobs.csv", index=False)

        # --- START: FULLY REVISED NAVIGATION LOGIC ---
        if len(jobs) < num_jobs:
            navigated = False
            
            # CASE 1: "Show more jobs" button (Infinite Scroll)
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                show_more_btn = driver.find_element(By.CSS_SELECTOR, "button[data-test='load-more']")
                
                if show_more_btn.is_enabled() and show_more_btn.is_displayed():
                    if verbose:
                        print(f"\nPagination: Clicking 'Show more jobs' to load more...")
                    show_more_btn.click()
                    time.sleep(4)
                    
                    # KEY FIX: Update the count of processed cards to the current total
                    scraped_card_count = len(all_job_cards) 
                    if verbose:
                        print(f"   - Updating scraped card count to {scraped_card_count}.")
                        
                    navigated = True
                    # 'continue' restarts the while loop. It will re-scan and
                    # slice all_job_cards starting from the new count.
                    continue 
            except:
                if verbose:
                    print("   - No 'Show more jobs' button found. Checking for 'Next' button...")

            # CASE 2: "See more jobs" link (New URL)
            if not navigated:
                try:
                    more_jobs_link = driver.find_element(By.XPATH, "//a[contains(., 'See more jobs')]")
                    new_url = more_jobs_link.get_attribute('href')
                    
                    if new_url:
                        if verbose:
                            print("\n" + "="*40)
                            print(f"NAV: No 'Next' buttons. Found 'See more jobs' link.")
                            print(f"     Navigating to new list: {new_url[:80]}...")
                            print("="*40)
                        
                        driver.get(new_url)
                        time.sleep(5) 
                        close_any_modal(driver) 
                        
                        # KEY FIX: Reset card count for the new page
                        scraped_card_count = 0
                        if verbose:
                            print("   - Resetting scraped card count to 0 for new URL.")
                            
                        page_num = 1 # Reset page counter
                        continue 
                    
                except NoSuchElementException:
                    if verbose:
                        print("\n✓ No 'Show more', 'Next', or 'See more' links/buttons found. Scraping complete.")
                    break 
                except Exception as e:
                    if verbose:
                        print(f"\nError in final navigation step: {e}")
                    break
            
            # This is the final exit if no navigation was successful
            if not navigated:
                print("\n✓ No navigation element found. Scraping complete.")
                break
        
        # --- END: FULLY REVISED NAVIGATION LOGIC ---

    print(f"\n{'='*70}")
    print(f"✅ Scraping complete! Collected {len(jobs)} jobs.")
    print(f"{'='*70}\n")
    
    # driver.quit() # Still commented out as in your code
    return pd.DataFrame(jobs)

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🔍 GLASSDOOR JOB SCRAPER")
    print("="*70 + "\n")
    
    df = get_jobs(
        keyword="data scientist", 
        num_jobs=2000, 
        headless=False, 
        verbose=True
    )
    print(df)
    
    if len(df) > 0:
        df.to_csv("glassdoor_jobs.csv", index=False)
        print(f"💾 Saved {len(df)} jobs to glassdoor_jobs.csv")
        print(f"\nColumns: {list(df.columns)}")
        print(f"\nFirst few jobs:")
        print(df[['Job Title', 'Company', 'Location']].head())
    else:
        print("❌ No jobs were scraped.")
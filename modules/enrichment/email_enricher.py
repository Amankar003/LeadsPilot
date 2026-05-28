import re
import json
import threading
import time
from datetime import datetime
from typing import List, Dict, Optional

import requests
import phonenumbers
from bs4 import BeautifulSoup
from email_validator import validate_email, EmailNotValidError

from config.database import SessionLocal
from modules.database.repositories import LeadRepository
from modules.database.models import Campaign, ScrapingJob, Lead
from utils.hash_utils import generate_lead_hash
from utils.constants import (
    ENRICHMENT_PENDING, ENRICHMENT_ENRICHED, ENRICHMENT_PARTIAL,
    ENRICHMENT_FAILED, ENRICHMENT_SKIPPED_GENERIC_EMAIL, ENRICHMENT_WEBSITE_NOT_FOUND
)

# Generic public email providers to skip enrichment for
GENERIC_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "protonmail.com"}

# Common pages to try besides homepage
COMMON_PATHS = ["/", "/about", "/about-us", "/contact", "/contact-us", "/services", "/our-services"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
}

EMAIL_COL_ALIASES = {"email", "email_address", "mail", "e-mail", "contact_email"}

PHONE_REGEX = re.compile(r"(\+?\d[\d\-\s\(\)\.]{6,}\d)")
URL_SCHEMES = ["https://", "https://www.", "http://", "http://www."]


def _normalize_email(raw: str) -> Optional[str]:
    try:
        res = validate_email(raw)
        return res.email
    except EmailNotValidError:
        return None


def _extract_domain(email: str) -> str:
    return email.split("@")[-1].lower().strip()


def _is_generic_domain(domain: str) -> bool:
    domain = domain.lower().strip()
    # Exact match or endswith generic (covers subdomains like mail.gmail.com)
    for g in GENERIC_DOMAINS:
        if domain == g or domain.endswith("." + g):
            return True
    return False


def _try_fetch(url: str, timeout: int = 8):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if r.status_code == 200 and 'text/html' in r.headers.get('Content-Type', ''):
            return r.text, r.url
    except Exception:
        return None, None
    return None, None


def _extract_json_ld(soup: BeautifulSoup) -> List[Dict]:
    data = []
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            j = json.loads(script.string or '{}')
            data.append(j)
        except Exception:
            continue
    return data


def _extract_business_name(soup: BeautifulSoup, domain: str) -> str:
    # 1. og:site_name
    og = soup.find('meta', property='og:site_name')
    if og and og.get('content'):
        return og.get('content').strip()

    # 2. og:title
    ogt = soup.find('meta', property='og:title')
    if ogt and ogt.get('content'):
        return ogt.get('content').strip()

    # 3. title tag
    if soup.title and soup.title.string:
        return soup.title.string.strip()

    # 4. first h1
    h1 = soup.find('h1')
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)

    # fallback: domain cleaned
    return domain.split('.')[0].capitalize()


def _extract_phones(text: str) -> List[str]:
    matches = set()
    for m in PHONE_REGEX.findall(text or ""):
        cleaned = re.sub(r"[\s\.\-()]+", "", m)
        # simple length filter
        if len(re.sub(r"\D", "", cleaned)) < 7:
            continue
        matches.add(m.strip())
    # Try to canonicalize using phonenumbers where possible but don't force country
    cleaned_list = []
    for raw in matches:
        parsed = None
        try:
            if raw.startswith('+'):
                pn = phonenumbers.parse(raw, None)
                if phonenumbers.is_possible_number(pn):
                    cleaned_list.append(phonenumbers.format_number(pn, phonenumbers.PhoneNumberFormat.E164))
                    continue
        except Exception:
            pass
        # fallback to raw
        cleaned_list.append(re.sub(r"\s+", " ", raw))
    # remove duplicates while preserving order
    seen = set()
    out = []
    for p in cleaned_list:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _extract_social_links(soup: BeautifulSoup) -> Dict[str, str]:
    social = {}
    for a in soup.find_all('a', href=True):
        href = a['href']
        if 'linkedin.com' in href and 'linkedin' not in social:
            social['linkedin'] = href
        if ('facebook.com' in href or 'fb.com' in href) and 'facebook' not in social:
            social['facebook'] = href
        if 'instagram.com' in href and 'instagram' not in social:
            social['instagram'] = href
        if ('twitter.com' in href or 'x.com' in href) and 'twitter' not in social:
            social['twitter'] = href
        if 'youtube.com' in href and 'youtube' not in social:
            social['youtube'] = href
    return social


def _extract_address_from_ld(json_ld_list: List[Dict]) -> Optional[str]:
    for j in json_ld_list:
        try:
            if isinstance(j, dict):
                # look for address in Organization or LocalBusiness
                if 'address' in j and isinstance(j['address'], dict):
                    addr = j['address']
                    parts = []
                    for k in ['streetAddress', 'addressLocality', 'addressRegion', 'postalCode', 'addressCountry']:
                        if k in addr:
                            parts.append(str(addr[k]))
                    if parts:
                        return ', '.join(parts)
        except Exception:
            continue
    return None


def _extract_services(soup: BeautifulSoup) -> List[str]:
    services = []
    headings = soup.find_all(re.compile('^h[1-6]$'))
    for h in headings:
        txt = h.get_text(strip=True).lower()
        if 'service' in txt or 'what we do' in txt or 'our services' in txt:
            # gather siblings until next heading
            sibling = h.find_next_sibling()
            collected = []
            while sibling and sibling.name and not re.match('^h[1-6]$', sibling.name):
                if sibling.name in ['ul', 'ol']:
                    for li in sibling.find_all('li'):
                        v = li.get_text(strip=True)
                        if v:
                            collected.append(v)
                elif sibling.name in ['p', 'div']:
                    v = sibling.get_text(strip=True)
                    if v:
                        collected.append(v)
                sibling = sibling.find_next_sibling()
            for c in collected:
                if c and c not in services:
                    services.append(c)
    return services


def _scrape_site_for_info(url: str) -> Dict:
    txt, final_url = _try_fetch(url)
    if not txt:
        return {}
    soup = BeautifulSoup(txt, 'lxml')
    json_ld = _extract_json_ld(soup)

    business_name = _extract_business_name(soup, final_url.split('//')[-1].split('/')[0])
    phones = _extract_phones(soup.get_text(separator=' '))
    social = _extract_social_links(soup)
    about = ''
    # try common about sections
    about_el = None
    for sel in ['#about', '.about', '.about-us', 'section.about', 'div.about']:
        about_el = soup.select_one(sel)
        if about_el:
            about = about_el.get_text(separator=' ', strip=True)
            break
    if not about:
        # try meta description
        md = soup.find('meta', attrs={'name': 'description'})
        if md and md.get('content'):
            about = md.get('content').strip()
    addr = _extract_address_from_ld(json_ld)
    services = _extract_services(soup)

    return {
        'business_name': business_name,
        'phones': phones,
        'social': social,
        'about': about,
        'address': addr,
        'services': services,
        'website': final_url
    }


def enrich_email_file(file_stream, file_name: str, campaign_name: str = 'Email Enrichment', category: str = 'General', location: str = '') -> Dict:
    """
    Entry point to process an uploaded CSV/Excel containing emails and perform enrichment.
    Returns a summary dict with counts.
    """
    import pandas as pd
    db = SessionLocal()
    summary = {
        'total_uploaded': 0,
        'valid_emails': 0,
        'generic_skipped': 0,
        'websites_found': 0,
        'enriched': 0,
        'partial': 0,
        'failed': 0,
        'added_count': 0,
        'updated_count': 0,
        'skipped_duplicates': 0
    }

    try:
        # Read file
        try:
            if file_name.lower().endswith('.csv'):
                df = pd.read_csv(file_stream)
            else:
                df = pd.read_excel(file_stream)
        except Exception as e:
            return {'error': f'Failed to read file: {e}'}

        # detect email column
        cols = list(df.columns)
        email_col = None
        norm_map = {c: str(c).lower().strip().replace(' ', '_').replace('-', '_') for c in cols}
        for orig, norm in norm_map.items():
            if norm in EMAIL_COL_ALIASES or 'email' in norm:
                email_col = orig
                break
        if email_col is None and df.shape[1] == 1:
            email_col = df.columns[0]

        if email_col is None:
            return {'error': 'Could not detect email column. Please name the column email or upload a single-column file of emails.'}

        raw_vals = df[email_col].astype(str).fillna('').str.strip()
        raw_vals = raw_vals[raw_vals != '']
        emails = []
        seen = set()
        for v in raw_vals.tolist():
            n = _normalize_email(v)
            if not n:
                continue
            if n.lower() in seen:
                continue
            seen.add(n.lower())
            emails.append(n)

        summary['total_uploaded'] = len(raw_vals)
        summary['valid_emails'] = len(emails)

        if not emails:
            return summary

        # Create campaign and job
        from modules.database.models import get_or_create_default_user
        user = get_or_create_default_user(db)
        from modules.database.repositories import CampaignRepository
        campaign = CampaignRepository(db).create(
            user_id=user.id,
            campaign_name=campaign_name,
            platform='email_enrichment',
            category=category,
            location=location or '',
            status='CREATED'
        )

        job = ScrapingJob(
            campaign_id=campaign.id,
            platform='email_enrichment',
            category=category,
            location=location or '',
            status='RUNNING',
            total_scraped=len(emails),
            total_saved=0
        )
        db.add(job)
        db.flush()

        repo = LeadRepository(db)

        for email in emails:
            try:
                domain = _extract_domain(email)
                # Skip generic
                if _is_generic_domain(domain):
                    # create or update lead but mark skipped
                    temp_name = email.split('@')[0] + ' @ ' + domain
                    lead_hash = generate_lead_hash(temp_name, None, None, location or '')

                    existing = repo.get_by_lead_hash(lead_hash)
                    if existing:
                        summary['skipped_duplicates'] += 1
                    else:
                        # create a lead record but mark skipped
                        lead_obj = Lead(
                            user_id=user.id,
                            campaign_id=campaign.id,
                            scraping_job_id=job.id,
                            business_name=temp_name,
                            phone=None,
                            email=email,
                            website=None,
                            address=None,
                            city=location or None,
                            source='email_enrichment_upload',
                            has_email=True,
                            has_phone=False,
                            has_website=False,
                            lead_hash=lead_hash,
                            status='NEW_LEAD',
                            enrichment_status=ENRICHMENT_SKIPPED_GENERIC_EMAIL,
                            enrichment_source='csv_upload'
                        )
                        db.add(lead_obj)
                        db.flush()
                        summary['generic_skipped'] += 1
                        summary['added_count'] += 1
                    continue

                # Try to find website
                site_found = False
                site_info = {}
                for scheme in URL_SCHEMES:
                    for path in COMMON_PATHS:
                        url = scheme + domain + path
                        txt, final = _try_fetch(url)
                        if txt:
                            site_found = True
                            site_info = _scrape_site_for_info(final)
                            break
                    if site_found:
                        break

                # Prepare temporary business name
                temp_name = email.split('@')[0] + ' @ ' + domain
                lead_hash = generate_lead_hash(temp_name, None, site_info.get('website') if site_info else None, location or '')

                # Check duplicates by email first
                if repo.check_duplicate(email=email):
                    # update missing fields on existing lead(s)
                    # fetch existing lead by email
                    existing = db.query(Lead).filter(Lead.email == email).first()
                    if existing:
                        update_fields = {}
                        if site_info.get('website') and not existing.website:
                            update_fields['website'] = site_info.get('website')
                        if site_info.get('business_name') and (not existing.business_name or existing.business_name.startswith(email.split('@')[0])):
                            update_fields['business_name'] = site_info.get('business_name')
                        if site_info.get('phones') and not existing.phone:
                            update_fields['phone'] = site_info.get('phones')[0]
                        if site_info.get('address') and not existing.address:
                            update_fields['address'] = site_info.get('address')
                        if site_info.get('social') and not existing.social_links:
                            update_fields['social_links'] = site_info.get('social')
                        if site_info.get('about') and not existing.about_text:
                            update_fields['about_text'] = site_info.get('about')
                        if site_info.get('services') and not existing.services:
                            update_fields['services'] = site_info.get('services')

                        if update_fields:
                            update_fields['enrichment_status'] = ENRICHMENT_ENRICHED if site_found else ENRICHMENT_WEBSITE_NOT_FOUND
                            update_fields['enrichment_source'] = 'csv_upload'
                            update_fields['enriched_at'] = datetime.utcnow()
                            repo.update(existing.id, **update_fields)
                            summary['updated_count'] += 1
                            if site_found:
                                summary['enriched'] += 1
                            else:
                                summary['failed'] += 1
                        else:
                            summary['skipped_duplicates'] += 1
                    continue

                # Not duplicate; create new lead
                # Check by lead_hash to avoid duplicates created earlier under different keys
                existing_by_hash = repo.get_by_lead_hash(lead_hash)
                if existing_by_hash:
                    update_fields = {}
                    if site_info.get('website') and not existing_by_hash.website:
                        update_fields['website'] = site_info.get('website')
                    if site_info.get('business_name') and (not existing_by_hash.business_name or existing_by_hash.business_name.startswith(email.split('@')[0])):
                        update_fields['business_name'] = site_info.get('business_name')
                    if site_info.get('phones') and not existing_by_hash.phone:
                        update_fields['phone'] = site_info.get('phones')[0]
                    if site_info.get('address') and not existing_by_hash.address:
                        update_fields['address'] = site_info.get('address')
                    if site_info.get('social') and not existing_by_hash.social_links:
                        update_fields['social_links'] = site_info.get('social')
                    if site_info.get('about') and not existing_by_hash.about_text:
                        update_fields['about_text'] = site_info.get('about')
                    if site_info.get('services') and not existing_by_hash.services:
                        update_fields['services'] = site_info.get('services')
                    if update_fields:
                        update_fields['enrichment_status'] = ENRICHMENT_ENRICHED if site_found else ENRICHMENT_WEBSITE_NOT_FOUND
                        update_fields['enrichment_source'] = 'csv_upload'
                        update_fields['enriched_at'] = datetime.utcnow()
                        repo.update(existing_by_hash.id, **update_fields)
                        summary['updated_count'] += 1
                        if site_found:
                            summary['enriched'] += 1
                        else:
                            summary['failed'] += 1
                        continue
                if site_found:
                    lead_obj = Lead(
                        user_id=user.id,
                        campaign_id=campaign.id,
                        scraping_job_id=job.id,
                        business_name=site_info.get('business_name') or temp_name,
                        phone=(site_info.get('phones')[0] if site_info.get('phones') else None),
                        email=email,
                        website=site_info.get('website'),
                        domain=domain,
                        address=site_info.get('address'),
                        city=location or None,
                        source='email_enrichment_upload',
                        has_email=True,
                        has_phone=bool(site_info.get('phones')),
                        has_website=True,
                        lead_hash=lead_hash,
                        status='NEW_LEAD',
                        enrichment_status=ENRICHMENT_ENRICHED,
                        enrichment_source='web_scrape',
                        enriched_at=datetime.utcnow(),
                        social_links=site_info.get('social') or {},
                        about_text=site_info.get('about') or None,
                        services=site_info.get('services') or []
                    )
                    db.add(lead_obj)
                    db.flush()
                    summary['added_count'] += 1
                    summary['websites_found'] += 1
                    summary['enriched'] += 1
                else:
                    # website not found
                    lead_obj = Lead(
                        user_id=user.id,
                        campaign_id=campaign.id,
                        scraping_job_id=job.id,
                        business_name=temp_name,
                        phone=None,
                        email=email,
                        website=None,
                        domain=domain,
                        address=None,
                        city=location or None,
                        source='email_enrichment_upload',
                        has_email=True,
                        has_phone=False,
                        has_website=False,
                        lead_hash=lead_hash,
                        status='NEW_LEAD',
                        enrichment_status=ENRICHMENT_WEBSITE_NOT_FOUND,
                        enrichment_source='csv_upload'
                    )
                    db.add(lead_obj)
                    db.flush()
                    summary['added_count'] += 1
                    summary['failed'] += 1

            except Exception as e:
                db.rollback()
                summary['failed'] += 1
                continue

        # finalize job
        job.total_saved = summary['added_count']
        job.status = 'COMPLETED'
        job.completed_at = datetime.utcnow()
        db.commit()

        return summary

    finally:
        db.close()


def enrich_file_background(file_stream, file_name, campaign_name='Email Enrichment', category='General', location=''):
    """Helper that runs enrichment in a background thread and returns the thread object."""
    t = threading.Thread(target=enrich_email_file, args=(file_stream, file_name, campaign_name, category, location), daemon=True)
    t.start()
    return t

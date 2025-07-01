import json
import sys
import os
from seleniumbase import SB
from bs4 import BeautifulSoup


def parse_business_details(html_content):
    """Parse business details from the HTML and return structured data"""
    soup = BeautifulSoup(html_content, 'html.parser')
    data = {}
    
    # Helper function to get text by label
    def get_text_by_label(label_text):
        label_elem = soup.find('span', string=lambda text: text and label_text in text)
        if label_elem:
            # Look for the value in the next cell/div
            parent_row = label_elem.find_parent('div', class_='row')
            if parent_row:
                value_divs = parent_row.find_all('div', class_='col-3')
                for i, div in enumerate(value_divs):
                    if label_elem.get_text() in div.get_text():
                        # Get the next div that contains the value
                        if i + 1 < len(value_divs):
                            value_elem = value_divs[i + 1].find('span', class_='swLabelDetailsBlack')
                            if value_elem:
                                return value_elem.get_text(strip=True)
        return None
    
    def get_address_text(label_text):
        label_elem = soup.find('span', string=lambda text: text and label_text in text)
        if label_elem:
            parent_row = label_elem.find_parent('div', class_='row')
            if parent_row:
                address_div = parent_row.find('div', class_='swLabelDetailsBlack')
                if address_div:
                    address_span = address_div.find('span', class_='swLabelWrap')
                    if address_span:
                        # Replace <br> with newlines and clean up
                        address_text = str(address_span)
                        address_text = address_text.replace('<br>', '\n').replace('<br/>', '\n')
                        soup_addr = BeautifulSoup(address_text, 'html.parser')
                        return soup_addr.get_text(strip=True)
        return None
    
    def get_registered_agent_info():
        reg_agent_divs = soup.find_all('div', class_='swLabelDetailsBlack')
        for div in reg_agent_divs:
            if div.find('a'):
                link = div.find('a')
                if 'RegisteredAgentDetail.aspx' in link.get('href', ''):
                    agent_name = link.get_text(strip=True)
                    address_span = div.find('span', class_='swLabelWrap')
                    if address_span:
                        address_text = str(address_span)
                        address_text = address_text.replace('<br>', ', ').replace('<br/>', ', ')
                        soup_addr = BeautifulSoup(address_text, 'html.parser')
                        agent_address = soup_addr.get_text(strip=True)
                        return {
                            "Name": agent_name,
                            "Address": agent_address
                        }
        return None

    # Extract basic business information
    data["Business Name"] = get_text_by_label("Name(s)")
    data["Charter Number"] = get_text_by_label("Charter No.")
    data["Type"] = get_text_by_label("Type")
    data["Status"] = get_text_by_label("Status")
    data["Domesticity"] = get_text_by_label("Domesticity")
    data["Home State"] = get_text_by_label("Home State")
    data["Date Formed"] = get_text_by_label("Date Formed")
    data["Duration"] = get_text_by_label("Duration")
    
    # Extract address information
    principal_address = get_address_text("Principal Office Address")
    if principal_address:
        data["Principal Office Address"] = principal_address
    
    # Extract registered agent information
    reg_agent = get_registered_agent_info()
    if reg_agent:
        data["Registered Agent"] = reg_agent
    
    # Extract filing information from the table
    filing_table = soup.find('table', class_='rgMasterTable')
    if filing_table:
        filings = []
        rows = filing_table.find('tbody').find_all('tr', class_=['rgRow', 'rgAltRow'])
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 6:
                filing = {
                    "Type": cells[3].get_text(strip=True) if len(cells) > 3 else "",
                    "Action": cells[4].get_text(strip=True) if len(cells) > 4 else "",
                    "Date Filed": cells[5].get_text(strip=True) if len(cells) > 5 else "",
                    "Effective Date": cells[6].get_text(strip=True) if len(cells) > 6 else ""
                }
                
                # Extract document link from the View Document button
                view_btn = cells[2].find('input', {'value': 'View Document'}) if len(cells) > 2 else None
                if view_btn and view_btn.get('onclick'):
                    onclick = view_btn.get('onclick')
                    # Extract document ID and version from: ShowFiledDocumentForBEFiling(135145946, 2)
                    import re
                    match = re.search(r'ShowFiledDocumentForBEFiling\((\d+),\s*(\d+)\)', onclick)
                    if match:
                        doc_id = match.group(1)
                        version = match.group(2)
                        document_url = f"https://bsd.sos.mo.gov/Common/CorrespondenceItemViewHandler.ashx?IsTIFF=true&filedDocumentid={doc_id}&version={version}"
                        filing["Document URL"] = document_url
                        filing["Document ID"] = doc_id
                        filing["Document Version"] = version
                
                filings.append(filing)
        if filings:
            data["Filed Documents"] = filings
    
    # Extract address history from the address grid
    address_table = soup.find('div', id=lambda x: x and 'BEAddressGrid' in x)
    if address_table:
        table = address_table.find('table', class_='rgMasterTable')
        if table:
            addresses = []
            rows = table.find('tbody').find_all('tr', class_=['rgRow', 'rgAltRow'])
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 5:
                    address_span = cells[2].find('span')
                    if address_span:
                        address_html = str(address_span)
                        address_html = address_html.replace('<br>', ', ').replace('<br/>', ', ')
                        soup_addr = BeautifulSoup(address_html, 'html.parser')
                        clean_address = soup_addr.get_text(strip=True)
                        
                        address_info = {
                            "Type": cells[1].get_text(strip=True),
                            "Address": clean_address,
                            "Since": cells[3].get_text(strip=True),
                            "To": cells[4].get_text(strip=True)
                        }
                        addresses.append(address_info)
            if addresses:
                data["Address History"] = addresses
    
    return data


def scrape_business_info(charter_number):
    """Scrape Missouri business entity information by charter number"""
    print(f"[INFO] Starting Missouri business entity search for: {charter_number}")
    
    # Missouri Business Entity Search URL
    MO_URL = "https://bsd.sos.mo.gov/BusinessEntity/BESearch.aspx?SearchType=3"
    
    with SB(uc=True, test=True, locale="en", maximize=True) as sb:
        sb.activate_cdp_mode(MO_URL)
        
        print("[INFO] Waiting for page to load and bypassing captcha/Cloudflare...")
        
        # Wait for the required input field to appear
        target_input = 'input[class="swRequiredTextbox form-control"]'
        while not sb.cdp.is_element_present(target_input):
            try:
                sb.uc_gui_click_cf()
                print("[INFO] Attempting to bypass Cloudflare...")
            except Exception as e:
                print(f"[INFO] Cloudflare bypass attempt: {e}")
                pass
            sb.cdp.sleep(1)
        
        print(f"✓ Found target input field: {target_input}")
        
        sb.cdp.type(target_input, charter_number)
        sb.cdp.click('a[title="Search"]')
        sb.cdp.click('a[title="Select the link to view the Full Details for this Business"]')
        
        sb.cdp.sleep(3)
        
        # Get the page source after navigation is complete
        html_content = sb.cdp.get_page_source()
        
        print(f"[INFO] Page source length: {len(html_content)} characters")
        print(f"[INFO] Parsing business details...")
        
        # Parse the business details
        business_data = parse_business_details(html_content)
        
        # Save to JSON file
        output_filename = f"missouri_business_info_{charter_number}.json"
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(business_data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Successfully extracted data and saved to {output_filename}")
        print(f"✓ Successfully processed charter number: {charter_number}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scraper.py <charter_number>")
        sys.exit(1)
    charter_number_arg = sys.argv[1]
    scrape_business_info(charter_number_arg) 
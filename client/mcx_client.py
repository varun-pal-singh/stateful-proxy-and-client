import requests
import json
from typing import Dict, Any

def load_credentials(file_path: str = "../config/credentials.json") -> Dict[str, Any]:
    """Load credentials from JSON file"""
    with open(file_path, 'r') as f:
        return json.load(f)

def make_mcx_margin_request(credentials: Dict[str, Any]) -> requests.Response:
    """
    Make POST request to MCX clearing margin utilization endpoint
    
    Args:
        credentials: Dictionary containing cookies and payload_tokens
        
    Returns:
        requests.Response object
    """
    
    # URL
    url = "https://eclear.mcxccl.com/Bancs/RSK/RSK335.do"
    
    # Headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) Gecko/20100101 Firefox/143.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://eclear.mcxccl.com",
        "Connection": "keep-alive",
        "Referer": "https://eclear.mcxccl.com/Bancs/RSK/RSK335.do?app=bancsapp?prefix=/RSK&page=/RSK335.do&confViewSize=22&reqType=0&mode=DEF_MODE&cParent=&parentName=blank&browserType=IE55&GuiWinName=RSK335&compname=RSK&locale=&winlocale=&over_ride_button=Cancel&AvlHt=726&AvlWd=983&tblWd=967&GuiBrowserInst=0&theme=black&confViewSize=22&pageId=RSK335&wintitle=Margin%20Utilization%20View&availHeight=820&availWidth=1067&tabid=2&tabId=panel2",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Priority": "u=0"
    }

    # {
#   "AlteonP": "BI1pZUNEqMARRScUPrUeWg$$",
#   "JSESSIONID": "0001yM1wiYyBx6q5G7-06bIr0Ji:-O2BCN8",
#   "TS01d67e35": "01de3801a585e35076b6512abe23204aa490f4bbb5d60985112aa78406cd4eb7c18603065166140522f684a35e427358113be816a42463d616a6466a0071d77d0f09b0a5edc3e381164c84ff1d8f3f004ac773917f",
#   "TS254a1510027": "08f91e7fa6ab200030c0214206635d3993fbd093741a15ff485bc29a3ac7b8a2ef0cb37f10f414d4088bd9e8211130005fa88faaa026bdfbe804c77d0417ff61643ae4f4f10f85c012894b339a657ec95fd82d5e63a92e1a50701e33628801b6",
#   "IXHRts": "1759482906778",
#   "rndaak": "5Hg1xYyM0kH4YOnpsw96zBJey",
#   "last_updated": "2025-10-03T14:45:09.860564Z"
# }
    
    # Cookies from credentials
    cookies = {}
    # cookies = credentials.get("cookies", {})
    cookies["AlteonP"] = credentials.get("AlteonP", "")
    cookies["JSESSIONID"] = credentials.get("JSESSIONID", "")
    cookies["TS01d67e35"] = credentials.get("TS01d67e35", "")
    cookies["TS254a1510027"] = credentials.get("TS254a1510027", "")
    
    # Payload tokens from credentials
    # payload_tokens = credentials.get("payload_tokens", {})
    # payload_tokens = {}
    ixhrts = credentials.get("IXHRts", "")
    rndaak = credentials.get("rndaak", "")
    
    # Construct payload data
    payload = {
        "propertyMap(MCB_SearchWC_wca_bpid_Cmb)": "DFLT",
        "MCB_SearchWC_wca_bpid": "",
        "propertyMap(MCB_SearchWC_wca_bpid_op)": "",
        "MCB_SearchWC_wca_actype": "",
        "propertyMap(MCB_SearchWC_wca_actype_op)": "",
        "propertyMap(MCB_SearchWC_wca_associatedtm_Cmb)": "DFLT",
        "MCB_SearchWC_wca_associatedtm": "",
        "propertyMap(MCB_SearchWC_wca_associatedtm_op)": "",
        "propertyMap(MCB_SearchWC_wca_associatedcm_Cmb)": "DFLT",
        "MCB_SearchWC_wca_associatedcm": "",
        "propertyMap(MCB_SearchWC_wca_associatedcm_op)": "",
        "MCB_SearchWC_wca_valuedate": "",
        "propertyMap(MCB_SearchWC_wca_valuedate_op)": "",
        "MCB_SearchWC_wca_category": "",
        "propertyMap(MCB_SearchWC_wca_category_op)": "",
        "MCB_SearchWC_wca_CMName": "DFLT",
        "propertyMap(MCB_SearchWC_wca_CMName_op)": "",
        "MCB_SearchWC_wca_TMName": "DFLT",
        "propertyMap(MCB_SearchWC_wca_TMName_op)": "",
        "MCB_SearchWC_wca_datedummy1": "",
        "propertyMap(MCB_SearchWC_wca_datedummy1_op)": "",
        "MCB_SearchWC_wca_datedummy2": "",
        "propertyMap(MCB_SearchWC_wca_datedummy2_op)": "",
        "GRID_RESPONSE": "RSK335_Table",
        "operationType": "ET",
        "searchClicked": "true",
        "PageNum": "0",
        "service": "qryMarginUtilView",
        "windowName": "RSK335",
        "MODE": "DEF_MODE",
        "compName": "RSK",
        "lgbinst": "0",
        "WRITE_APP": "true",
        "REQ_TYPE": "0",
        "sQuery": "Client Code  Equals  DFLT AND TM / CP  Equals  DFLT AND CM  Equals  DFLT",
        "AvlWd": "969",
        "tblWd": "947",
        "MCBrowserEventInformation": "sourceElementName~|~Search#*#eventType~|~click#*#butId~|~null",
        "IXHRts": ixhrts,  # Dynamic value from credentials
        "XHR": "true",
        "rndaak": rndaak,  # Dynamic value from credentials
        "theme": "black",
        "tabId": "panel2",
        "mode": "DEF_MODE",
        "GuiBrowserInst": "0",
        "parentName": "blank",
        "parentToChildCopyData": "",
        "childToParentCopyData": "",
        "parentTabId": "",
        "childToParentJavaCopyFlag": "",
        "openedFromBtn": "",
        "confViewSize": "22",
        "favouriteData": "",
        "ExtnAttrDropDownValueDesc": "{}",
        "ExtnRadioValues": "{}",
        "butvalue": "",
        "reqType": "1",
        "childTabId": "",
        "popupctrl": "",
        "callPopUp": "",
        "frombsle": "NO",
        "fromTblBtn": "NO",
        "functionName": "",
        "ifCallPaint": "0",
        "controlName": "",
        "param": "",
        "WindowName": "",
        "parentSelectedRow": "",
        "browserType": "IE55",
        "GuiWinName": "RSK335",
        "compname": "RSK",
        "locale": "",
        "winlocale": "",
        "SortedColumnName": "",
        "over_ride_button": "Cancel",
        "parentToChildData": ""
    }
    
    # Make POST request
    response = requests.post(
        url=url,
        headers=headers,
        cookies=cookies,
        data=payload,
        verify=True  # Set to False if SSL verification fails
    )
    
    return response

def main():
    """Main execution function"""
    try:
        # Load credentials
        credentials = load_credentials("credentials.json")
        
        # Make request
        print("Making POST request to MCX clearing...")
        response = make_mcx_margin_request(credentials)
        
        # Display results
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"\nResponse Content (first 500 chars):")
        print(response.text[:500])
        
        # Save full response if needed
        with open("response_output.txt", "w", encoding="utf-8") as f:
            f.write(response.text)
        print("\nFull response saved to 'response_output.txt'")
        
        return response
        
    except FileNotFoundError:
        print("Error: credentials.json file not found!")
        print("\nCreate a credentials.json file with this structure:")
        print(json.dumps({
            "cookies": {
                "AlteonP": "your_value",
                "JSESSIONID": "your_value",
                "TS01d67e35": "your_value",
                "TS254a1510027": "your_value"
            },
            "payload_tokens": {
                "IXHRts": "your_timestamp",
                "rndaak": "your_random_token"
            }
        }, indent=2))
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        raise

if __name__ == "__main__":
    main()

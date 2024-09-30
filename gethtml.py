import re
import sys
from bs4 import BeautifulSoup


data = open("good.html").read()
parsed_html = BeautifulSoup(data, "html.parser")
output_data = {
    "Class": "",
    "Location Address": "",
    "Property Description": "",
    "Primary Building SQ FT": "",
    "Year Built": "",
    "Lot Size (Acres)": "",
    "Land Use Code": "",
    "Style": "",
    "Owner": "",
    "Owner Mailing Address": "",
    "Unit": "",
    "City": "",
    "State": "",
    "Zip Code": "",
    "Other Mailing Address": "",
}
div_ids = ["datalet_div_1", "datalet_div_2", "datalet_div_4", "datalet_div_6"]

key = ""
for div_id in div_ids:
    div = parsed_html.body.find(id=div_id)
    if not div:
        print("ERROR: no data in file")
        sys.exit(0)
    for item in div.find_all("td"):
        if item.string in output_data:
            key = item.string
        elif key:
            if item.string == "\xa0":
                output_data[key] = "N/A"
            else:
                output_data[key] = item.string
            key = ""

parcelid = parsed_html.body.find(string=re.compile("^PARID: ")).split()[1]

output_data["PARID"] = parcelid
print(output_data)

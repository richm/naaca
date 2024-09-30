import argparse
import csv
import os
import requests
import shapefile
import shutil
import mechanize
import logging
import json
import time
import zipfile
import re
import sys
from bs4 import BeautifulSoup
from pyproj import CRS, Transformer
from operator import itemgetter
from shapely.geometry import Point
from shapely.geometry.polygon import Polygon

baseurl = "https://api-cat.usps.com"
#baseurl = "https://api.usps.com"

token_url = f"{baseurl}/oauth2/v3/token"
address_url = f"{baseurl}/addresses/v3/address"

bernco_map_url = "https://pdsmaps.bernco.gov/website/Downloads/DownloadGISData/CountyBaseMap.zip"
neighbors_map_url = "https://pdsmaps.bernco.gov/website/Downloads/DownloadGISData/NeighborhoodAssociations.zip"

assessor_url = "https://assessor.bernco.gov/public.access/search/CommonSearch.aspx?mode=realprop"

# map of GIS data field to what we want to use in our data
gis_fieldmap = {
    "LOT": "LOT",
    "BLOCK": "BLOCK",
    "SUBDIVISIO": "PROP_DESC_GIS",
    "STREETNUMB": "PROP_STREET_NO",
    "STREETNAME": "PROP_STREET_NAME",
    "STREETDESI": "STREET_TYPE",
    "STREETQUAD": "STREET_DIRECTION",
    "PIN": "PROP_ID_BERNCO",
    "last_edi_1": "UPDATE_DATE_GIS",
    "Jurisdicti": "JURISDICTION",
    "Shape_Leng": "PROP_PERIMETER",
    "Shape_Area": "PROP_AREA",
    "ADDRESS": "PROP_ADDRESS_GIS",
    "GISACRES": "PROP_ACRES_GIS",
}

# map of assessor html fields to what we want to use
assessor_fieldmap = {
    "Class": "PROP_CLASS_OBA",
    "Location Address": "PROP_ADDRESS_OBA",
    "Property Description": "PROP_DESC_OBA",
    "Primary Building SQ FT": "PROP_BLDG_SQFT",
    "Year Built": "PROP_BLDG_YEAR",
    "Lot Size (Acres)": "PROP_AREA_OBA",
    "Land Use Code": "PROP_USAGE_OBA",
    "Style": "PROP_STYLE_OBA",
    "Owner": "PROP_OWNER_NAME",
    "Owner Mailing Address": "PROP_OWNER_ADDRESS",
    "Unit": "PROP_OWNER_UNIT",
    "City": "PROP_OWNER_CITY",
    "State": "PROP_OWNER_STATE",
    "Zip Code": "PROP_OWNER_ZIP",
    "Other Mailing Address": "PROP_OWNER_OTHER_ADDRESS",
}

# fields to output, in order
output_fields = [
    "PROP_ADDRESS",  # the most accurate address - USPS, or GIS if not available
    "SOLAR",  # Y or N
    "PROP_TYPE",  # V for vacant, C for construction, R for residential, N for non-residential (church, business, water tank, etc.)
    "LOT",
    "BLOCK",
    "PROP_DESC_GIS",
    "PROP_PERIMETER",
    "PROP_AREA",
    "PROP_ACRES_GIS",
    "PROP_ID_BERNCO",
    "UPDATE_DATE_GIS",
    "JURISDICTION",
    "GMAP_LINK",
    "LOCATION",
    "CENTER_LONG",
    "CENTER_LAT",
    "PROP_STREET_NO",
    "PROP_STREET_NAME",
    "STREET_TYPE",
    "STREET_DIRECTION",
    "PROP_ADDRESS_GIS",
    "PROP_ADDRESS_USPS",
    "PARCEL_ID",
    "PROP_CLASS_OBA",
    "PROP_ADDRESS_OBA",
    "PROP_DESC_OBA",
    "PROP_BLDG_SQFT",
    "PROP_BLDG_YEAR",
    "PROP_AREA_OBA",
    "PROP_USAGE_OBA",
    "PROP_STYLE_OBA",
    "PROP_OWNER_NAME",
    "PROP_OWNER_ADDRESS",
    "PROP_OWNER_UNIT",
    "PROP_OWNER_CITY",
    "PROP_OWNER_STATE",
    "PROP_OWNER_ZIP",
    "PROP_OWNER_OTHER_ADDRESS",
]

# raised when assessor search form returns that it is unavailable/overloaded
# in this case, we need to do exponential backoff
class UnavailableException(Exception): pass
# raised when assessor search result html cannot be parsed
# write bad.html file and exit
class BadFormatException(Exception): pass

def get_shapefile_crs(url, name):
    if os.path.exists(f"{name}.zip"):
        os.unlink(f"{name}.zip")
    response = requests.get(url)
    # get zip file
    with open(f"{name}.zip", "wb") as fd:
        for chunk in response.iter_content(chunk_size=128):
            fd.write(chunk)
    # remove existing name data
    if os.path.exists(name):
        shutil.rmtree(name)

    # extract zip files
    os.mkdir(name)
    with zipfile.ZipFile(f"{name}.zip", "r") as zf:
        zf.extractall(name)

    sf = shapefile.Reader(f"{name}/{name}")
    crs = CRS(open(f"{name}/{name}.prj").read())
    return sf, crs


# there are some bogus records in the bernco data
def is_valid_naaca_property(sf, naaca_poly):
    if sf.record.STREETNUMB == 0:
        return False
    if sf.record.LOT.find("WELL SITE") > -1:
        return False
    if sf.record.LOT.find("LA CUEVA DIKE") > -1:
        return False
    if sf.record.SUBDIVISIO.startswith("AMAFCA"):
        return False
    if sf.record.SUBDIVISIO.startswith("PRIMROSE POINTE"):
        return False
    if sf.record.SUBDIVISIO.startswith("N ABQ ACRES"):
        return True
    point1 = Point(sf.shape.points[0])
    point2 = Point(sf.shape.points[2])
    if naaca_poly.contains(point1) or naaca_poly.contains(point2):
        return True
    return False

# return (lat, long) of the centroid of the polygon described by points
# points is a list of tuple pairs of (lat, long)
# assumes points[0] == points[-1] so doesn't use points[-1]
def get_centroid(points):
    n = len(points)-1
    lat = sum([ii[0] for ii in points[:n]])/float(n)
    long = sum([ii[1] for ii in points[:n]])/float(n)
    return lat, long

token = ""
def usps_get_token(args):
    global token
    if not token:
        req = {
            "grant_type": "client_credentials",
            "client_id": args.usps_key,
            "client_secret": args.usps_secret,
        }
        headers = {
            "Content-Type": "application/json"
        }
        resp = requests.post(token_url, data=json.dumps(req), headers=headers)
        token = resp.json()["access_token"]
    return token


# returns the official usps form of the given address
# in some cases, the difference is that bernco uses AV but USPS uses AVE
# usually if the address is not found it means that it is a vacant lot that has
# no USPS service
def usps_address(args, address):
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + usps_get_token(args),
    }

    req_data = {"streetAddress": address, "state": "NM", "ZIPCode": "87122"}
    resp = requests.get(address_url, headers=headers, params=req_data)
    if resp.status_code >= 400 and resp.status_code <= 404:
        logging.error("Request for address [%s] failed: %d [%s]", address, resp.status_code, resp.text)
        return ""
    backoff = 60
    while resp.status_code != 200:
        logging.info("Request for address [%s] failed, will retry in [%d] seconds: %d [%s]", address, backoff, resp.status_code, resp.text)
        time.sleep(backoff)
        resp = requests.get(address_url, headers=headers, params=req_data)
        backoff *= 2
    resp_data = resp.json()
    if address != resp_data["address"]["streetAddress"]:
        logging.info("Address %s is not the same as the USPS address %s", address, resp_data["address"]["streetAddress"])
    return resp_data["address"]["streetAddress"]


def build_record_from_bernco_sr(sr, xfrm, record_exists):
    if sr.record.STREETNUMB and sr.record.STREETNAME:
        addr = f"{sr.record.STREETNUMB} {sr.record.STREETNAME}"
        if sr.record.STREETDESI:
            addr += f" {sr.record.STREETDESI}"
        if sr.record.STREETQUAD:
            addr += f" {sr.record.STREETQUAD}"
        if not addr == sr.record.ADDRESS:
            logging.warning("address not equal: [%s] != [%s]", addr, sr.record.ADDRESS)
    if sr.record.APARTMENT:
        logging.warning("apartment: [%s] is an apartment [%s]", sr.record.ADDRESS, sr.record.APARTMENT)
    output_rec = {}
    for gis_field, our_field in gis_fieldmap.items():
        output_rec[our_field] = getattr(sr.record, gis_field, "NOT_FOUND")
    lat_long_list = [xfrm.transform(*point) for point in sr.shape.points]
    output_rec["LOCATION"] = ",".join("%s,%s" % tup for tup in lat_long_list)
    center_lat, center_long = get_centroid(lat_long_list)
    # this displays item zoomed and centered but doesn't put marker on center of property
    # hard to tell which property is being examined especially in subdivisions
    # output_rec["GMAP_LINK"] = "https://www.google.com/maps/@?api=1&map_action=map&center=%s,%s&zoom=20&basemap=satellite" % (center_lat, center_long)
    output_rec["GMAP_LINK"] = "https://www.google.com/maps?q=%s,%s" % (center_lat, center_long)
    output_rec["CENTER_LONG"] = center_long  # for sorting
    output_rec["CENTER_LAT"] = center_lat  # for sorting
    if record_exists:  # don't update manually maintained fields in existing record
        if sr.record.STREETNUMB == 99999:  # usually vacant lots have not been assigned a streetnum
            output_rec["SOLAR"] = "N"
            output_rec["PROP_TYPE"] = "V"
        else:
            output_rec["SOLAR"] = "N"
            output_rec["PROP_TYPE"] = "R"
    return output_rec


def refresh_data_from_bernco_gis(args, output_data):
    bernco_sf, bernco_crs = get_shapefile_crs(bernco_map_url, "CountyBaseMap")
    neighbors_sf, neighbors_crs = get_shapefile_crs(neighbors_map_url, "NeighborhoodAssociations")

    # find NAACA shape record
    naaca_sr = None
    for ii in neighbors_sf.shapeRecords():
        if ii.record.Name == "North Albuquerque Acres":
            naaca_sr = ii
            break

    # create a polygon
    naaca_poly = Polygon(naaca_sr.shape.points)

    # find all of the NAACA records
    naaca_srs = [ii for ii in bernco_sf.shapeRecords() if is_valid_naaca_property(ii, naaca_poly)]

    # map bernco gis cartesian x/y to lat/long
    latlong_crs = CRS("WGS84")
    xfrm = Transformer.from_crs(bernco_crs, latlong_crs)

    for ii in naaca_srs:
        prop_id = ii.record.PIN
        rec = build_record_from_bernco_sr(ii, xfrm, prop_id in output_data)
        output_data.setdefault(prop_id, {}).update(rec)
        rec = output_data[prop_id]

        if args.usps_normalize and not "PROP_ADDRESS_USPS" in rec:
            if rec["PROP_STREET_NO"] != 99999 and rec["PROP_ADDRESS_GIS"]:
                rec["PROP_ADDRESS_USPS"] = usps_address(args, rec["PROP_ADDRESS_GIS"])
            else:
                rec["PROP_ADDRESS_USPS"] = ""
            # set the PROP_ADDRESS to the USPS one if available
            if rec["PROP_ADDRESS_USPS"]:
                rec["PROP_ADDRESS"] = rec["PROP_ADDRESS_USPS"]
            else:
                rec["PROP_ADDRESS"] = rec["PROP_ADDRESS_GIS"]
            # throttle so as not to overload the system or get us locked out
            time.sleep(2)


def parse_html(data):
    parsed_html = BeautifulSoup(data, "html.parser")

    output_data = {}
    # first check if not found
    not_found_str = "Your search did not find any records"
    not_found = parsed_html.body.find(string=re.compile(not_found_str))
    if not_found:
        return output_data

    # next check if unavailable/overloaded
    unavail_str = "The System is currently unavailable due to maintenance.  Please check again later."
    unavailable = parsed_html.body.find(string=re.compile(unavail_str))
    if unavailable:
        raise UnavailableException("the system is unavailable")
    div_ids = ["datalet_div_1", "datalet_div_2", "datalet_div_4", "datalet_div_6"]

    key = ""
    for div_id in div_ids:
        div = parsed_html.body.find(id=div_id)
        if not div:
            raise BadFormatException(f"ERROR: invalid format - could not find div {div_id} in data")
        for item in div.find_all("td"):
            if item.string in assessor_fieldmap:
                key = assessor_fieldmap[item.string]
            elif key:
                if item.string == "\xa0":
                    output_data[key] = ""
                else:
                    output_data[key] = item.string
                key = ""

    parcel_id = parsed_html.body.find(string=re.compile("^PARID: ")).split()[1]

    output_data["PARCEL_ID"] = parcel_id
    return output_data


def refresh_data_from_assessor(args, output_data):
    return  # they seemed to have disabled access for non-browsers
    # will need to try again later?  or workaround block?
    br = mechanize.Browser()
    br.set_handle_robots(False)   # ignore robots
    br.set_handle_refresh(False)  # can sometimes hang without this
    br.set_handle_redirect(True)
    br.addheaders = [('User-agent', 'Google chrome')]
    br.open(assessor_url)

    # first page is the disclaimer that we have to click Agree to continue
    br.select_form(name="Form1")
    req = br.click(name="btAgree")
    br.open(req)

    sleep_time = 10  # seconds
    for rec in output_data.values():
        street_num = str(rec.get("PROP_STREET_NO"))
        street_name = rec.get("PROP_STREET_NAME")
        if not "PARCEL_ID" in rec and street_num != "99999" and street_name:
            while True:  # do in loop so we can retry
                # select search form
                br.select_form(name="frmMain")
                br.form["inpNo"] = street_num
                br.form["inpStreet"] = street_name
                req = br.click(name="btSearch")
                resp = br.open(req)
                data = resp.read().decode("utf-8")
                # go back to previous page to search again
                br.back()
                try:
                    assessor_rec = parse_html(data)
                    sleep_time = 10
                    break
                except UnavailableException:
                    sleep_time *= 2
                    logging.info("assessor record for [%s %s] not read due to unavailable - sleep %d seconds and retry . . .", street_num, street_name, sleep_time)
                    time.sleep(sleep_time)  # throttle to avoid DoS
                    continue
                except BadFormatException:
                    logging.error("invalid assessor record for [%s %s]", street_num, street_name)
                    with open("error.html", "w") as eh:
                        eh.write(data)
                    raise
            if assessor_rec:
                logging.debug("found assessor record for [%s %s]: [%s]", street_num, street_name, str(assessor_rec))
                rec.update(assessor_rec)
            else:
                logging.info("assessor record for [%s %s] was not found - will have to manually determine parcel id", street_num, street_name)
            time.sleep(sleep_time)  # throttle to avoid DoS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--naaca-csv-in",
        type=str,
        default=os.environ.get("NAACA_CSV_IN"),
        help="Path/filename for naaca.csv input",
    )
    parser.add_argument(
        "--naaca-csv-out",
        type=str,
        default=os.environ.get("NAACA_CSV_OUT", "naaca.csv"),
        help="Path/filename for naaca.csv output",
    )
    parser.add_argument(
        "--usps-key",
        type=str,
        default = os.environ.get("USPS_KEY"),
        help="Consumer key for USPS API - only needed if normalizing addresses",
    )
    parser.add_argument(
        "--usps-secret",
        type=str,
        default = os.environ.get("USPS_SECRET"),
        help="Consumer secret for USPS API - only needed if normalizing addresses",
    )
    parser.add_argument(
        "--usps-normalize",
        default=False,
        action="store_true",
        help="If PROP_ADDRESS_USPS is empty, get the address - default is to not to",
    )
    parser.add_argument(
        "--refresh",
        default=False,
        action="store_true",
        help="If true, redownload all data an reconstruct - will replace given naaca input data",
    )
    parser.add_argument(
        "--debug",
        default=False,
        action="store_true",
        help="Turn on debug logging.",
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    # key is Property ID - value is record
    naaca_data_by_prop_id = {}
    if args.naaca_csv_in:
        reader = csv.DictReader(open(args.naaca_csv_in, newline=""))
        for row in reader:
            prop_id = row.get("PROP_ID_BERNCO")
            if prop_id:
                naaca_data_by_prop_id[prop_id] = row
            else:
                logging.error("Row has no PROP_ID_BERNCO: %s", row)

    if args.refresh:
        refresh_data_from_bernco_gis(args, naaca_data_by_prop_id)
        refresh_data_from_assessor(args, naaca_data_by_prop_id)

    with open(args.naaca_csv_out, "w", newline="") as ff:
        csvwriter = csv.DictWriter(ff, output_fields)
        csvwriter.writeheader()
        for rec in sorted(naaca_data_by_prop_id.values(), key=itemgetter("PROP_STREET_NAME", "PROP_STREET_NO", "CENTER_LONG")):
            csvwriter.writerow(rec)


if __name__ == "__main__":
    sys.exit(main())

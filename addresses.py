import json
import yaml
import time
import requests

cfg = yaml.safe_load(open(".config.yml"))
consumer_key = cfg["usps_consumer_key"]
consumer_secret = cfg["usps_consumer_secret"]

baseurl = "https://api-cat.usps.com"
#baseurl = "https://api.usps.com"

token_url = f"{baseurl}/oauth2/v3/token"
address_url = f"{baseurl}/addresses/v3/address"

req = {
    "grant_type": "client_credentials",
    "client_id": consumer_key,
    "client_secret": consumer_secret,
}
headers = {
    "Content-Type": "application/json"
}
resp = requests.post(token_url, data=json.dumps(req), headers=headers)

token = resp.json()["access_token"]
headers["Authorization"] = "Bearer " + token

starting_num = 10900
street = "SAN ANTONIO DR NE"
# the NAACA street numbers are not sequential
nums = [1, 3, 5, 7, 9, 11, 13, 15, 19, 21, 25, 29, 31, 33, 41, 51, 61, 71, 75]

def naaca_street_nums(start, end):
    for hun in range(start, end, 100):
        for num in nums:
            yield hun + num


def is_valid_address(resp_data):
    return resp_data["additionalInfo"].get("DPVConfirmation") == "Y"


for num in naaca_street_nums(starting_num, 11000):
    req_data = {"streetAddress": f"{num} {street}", "state": "NM", "ZIPCode": "87122"}
    resp = requests.get(address_url, headers=headers, params=req_data)
    backoff = 60
    while resp.status_code != 200:
        print(f"Request for {num} {street} failed: {resp.status_code} {resp.text}")
        time.sleep(backoff)
        resp = requests.get(address_url, headers=headers, params=req_data)
        backoff *= 2
    resp_data = resp.json()
    print(resp_data)
    if is_valid_address(resp_data):
        print(f"{resp_data['address']['streetAddress']}")
    else:
        print(f"{num} {street} either does not exist or is a vacant lot")
    time.sleep(5)

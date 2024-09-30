import mechanize
import sys
import logging

# logger = logging.getLogger("mechanize")
# logger.addHandler(logging.StreamHandler(sys.stdout))
# logger.setLevel(logging.DEBUG)

br = mechanize.Browser()
url = "https://assessor.bernco.gov/public.access/search/CommonSearch.aspx?mode=realprop"
br.set_handle_robots(False)   # ignore robots
br.set_handle_refresh(False)  # can sometimes hang without this
br.set_handle_redirect(True)
br.addheaders = [('User-agent', 'Firefox')]
br.open(url)

# first page is the disclaimer that we have to click Agree to continue
br.select_form(name="Form1")
req = br.click(name="btAgree")
br.open(req)

# next, select search form
br.select_form(name="frmMain")
br.form["inpNo"] = "10901"
br.form["inpStreet"] = "SAN ANTONIO"
req = br.click(name="btSearch")
resp = br.open(req)
data = resp.read().decode("utf-8")
print(data)

# br.back()
# br.select_form(name="frmMain")
# br.form["inpNo"] = "10901"
# br.form["inpStreet"] = "SAN BERNARDINO"
# req = br.click(name="btSearch")
# resp = br.open(req)
# data = resp.read().decode("utf-8")
# print(data)

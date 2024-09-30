## NAACA GIS data

### Bernco

https://www.bernco.gov/planning/gis-overview/download-gis-data/
Neighborhood Associations: https://pdsmaps.bernco.gov/website/Downloads/DownloadGISData/NeighborhoodAssociations.zip
Property Record lookup: https://assessor.bernco.gov/public.access/search/commonsearch.aspx?mode=realprop
Map Gallery: https://www.bernco.gov/planning/gis-overview/map-gallery/

assessor information:
https://assessor.bernco.gov/public.access/search/commonsearch.aspx?mode=realprop
enter num, street or parcel id
gives you detailed property information
click on Satellite view to get up-to-date and historical images

how to get parcel id and other data
go to https://experience.arcgis.com/experience/9248998e85dd4a24a36bbaa01eaf1779
click on property - this will give you parcel ID which you can then plug into assessor information
you can also click on the box with the 4 circles ("Actions") - go to Export - download GeoJSON to get property boundary in lat, long pairs

This data is available for a fee

### CABQ

https://www.cabq.gov/gis/geographic-information-systems-data
Shapefile: http://coagisweb.cabq.gov/datadownload/nbr.zip
KMZ: http://coagisweb.cabq.gov/datadownload/NeighborhoodAssociations.kmz

## USPS

Getting Started: https://developer.usps.com/getting-started
Developer APIs: https://developer.usps.com/apis?page=0
Examples: https://github.com/USPS/api-examples

## python ShapeFiles processing

https://pythonhosted.org/Python%20Shapefile%20Library/
https://github.com/GeospatialPython/pyshp

## python BeautifulSoup HTML processing

https://beautiful-soup-4.readthedocs.io/en/latest/#searching-the-tree

## python mechanize website interaction

https://mechanize.readthedocs.io/en/latest/index.html

## Design

Property ID is assigned by Bernco - each lot gets a unique property id
Parcel ID is assigned by Assessor - multiple lots can be joined together into a single parcel and assigned a Parcel ID

So a single "house" may have a single Parcel ID and multiple Property IDs

get a list of all NAACA addresses by going through CountyBaseMap ShapeFile and
grab all record.SUBDIVISIO.startswith("N ABQ ACRES") - this will contain the
following data in the record:

* LOT  # e.g. 20
* BLOCK  # e.g. 30
* SUBDIVISIO  # e.g. N ABQ ACRES TR 3 UNIT 2
* STREETNUMB  # e.g. 11000
* STREETNAME  # e.g. SAN BERNARDINO
* STREETDESI  # e.g. DR, AVE, CT, etc.
* STREETQUAD  # e.g. NE
* APARTMENT  # probably not used
* PIN  # not sure what can be used for
* created_us  # who created this record
* created_da  # when record was created
* last_edite  # who last edited the record
* last_edi_1  # date of last edit - python datetime format
* Jurisdicti  # e.g. County
* Shape_Leng  # lot perimeter in feet
* Shape_Area  # lot area in sq. feet
* ADDRESS  # canonical address format
* GISACRES  # acreage of property

The corresponding shape will have the cartesian coordinates of the lot corners
which can be converted to lat/long with pyproj:

```
from pyproj import CRS, Transformer

bernco_crs = CRS(open("CountyBaseMap/CountyBaseMap.prj").read())
latlong_crs = CRS("WGS84")
xfrm = Transformer.from_crs(bernco_crs, latlong_crs)
lat, long = xfrm.transform(naaca_srs[0].shape.points[0])
```

convert points to lat, long

convert ADDRESS to USPS format - store as new field USPS_ADDRESS

Using STREETNUMB and STREETNAME lookup these fields from bernco

* Class  # e.g. Residential
* Location Address  # probably same as ADDRESS above
* Property Description  # similar to SUBDIVISIO e.g. * 026 003NORTH ALBQ ACRES TR3 UNIT #2
* Primary Building SQ FT  # e.g. 3882
* Year Built  # e.g. 2001
* Lot Size (Acres)  # same as GISACRES except more resolution
* Land Use Code  # e.g. RESIDENTIAL IMPROVED or VACANT ...
* Style  # e.g. STANDARD
* Owner  # name, trust, business e.g. MEGGINSON RICHARD A & VALENCIA PEGGY J TRUSTEE MEGGINSON/VALENCIA TRUST
* Owner Mailing Address  # number and street
* Unit  # e.g. apt no, unit no
* City
* State
* Zip Code
* Other Mailing Address
* PARID  # e.g. 102106342043810410

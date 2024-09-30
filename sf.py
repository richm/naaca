import shapefile
from pyproj import CRS, Transformer

# map of all records in county
bernco_sf = shapefile.Reader("CountyBaseMap/CountyBaseMap")
# map of all NAs
na_sf = shapefile.Reader("NeighborhoodAssociations/NeighborhoodAssociations")

# find shape and record for NAACA
naaca_srs = [ii for ii in bernco_sf.shapeRecords() if ii.record.SUBDIVISIO.startswith("N ABQ ACRES")]

# naaca_srs[0].record.as_dict()
# {'LOT': '30', 'BLOCK': '19', 'SUBDIVISIO': 'N ABQ ACRES TR 3 UNIT 2',
#  'STREETNUMB': 11009, 'STREETNAME': 'SAN ANTONIO', 'STREETDESI': 'DR', 'STREETQUAD': 'NE',
#  'APARTMENT': '', 'PIN': '166531', 'created_us': '', 'created_da': None, 'last_edite': 'TGAULDEN', 'last_edi_1': datetime.date(2018, 10, 8),
#  'Jurisdicti': 'County', 'Shape_Leng': 789.441262392, 'Shape_Area': 37507.9830461, 'ADDRESS': '11009 SAN ANTONIO DR NE', 'GISACRES': 0.86}
# PIN is Property Identification Number - don't know how it relates to Parcel ID - maybe not
# >>> naaca_srs[0].shape
# Shape #234: POLYGON
# note - POLYGON means first point is same as last point for a closed shape - which is why the rectangle has 5 points in shape.points
# >>> naaca_srs[0].shape.points
# [(1550429.082728263, 1525972.7344039455), (1550294.1328669302, 1525973.7560554445), (1550295.8579290956, 1526207.6712700278), (1550430.8061500117, 1526206.6476500332), (1550429.082728263, 1525972.7344039455)]

bernco_crs = CRS(open("CountyBaseMap/CountyBaseMap.prj").read())
latlong_crs = CRS("WGS84")

xfrm = Transformer.from_crs(bernco_crs, latlong_crs)

lat, long = xfrm.transform(naaca_srs[0].shape.points[0])

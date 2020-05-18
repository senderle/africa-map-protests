import itertools
import math
import csv

from collections import defaultdict, Counter

import shapefile
import pycountry
from reverse_geocoder import search as reverse_geo

# from shapely.geometry import Point, Polygon
import pandas
from bokeh.io import show, output_file
from bokeh.models import (
    LogColorMapper, LinearColorMapper, Circle, InvertedTriangle,
    ColumnDataSource
)
from bokeh.palettes import Blues8 as palette
from bokeh.plotting import figure
from bokeh.tile_providers import (
    CARTODBPOSITRON_RETINA,
    STAMEN_TERRAIN_RETINA,
    STAMEN_TONER,
    ESRI_IMAGERY,
    OSM,
    get_provider
)

# This is the function for making the map of africa graph


def lat_lon_to_web_mercator(lon, lat):
    x = lon * 20037508.34 / 180
    y = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180)
    y = y * 20037508.34 / 180
    return x, y


def safe_lt(comp):
    def comp_func(val):
        try:
            return float(val) < comp
        except ValueError:
            return False
    return comp_func


def load_shape_records():
    # importing shp and dbf

    # shp = open("World-Provinces/africa.shp", "rb")
    # dbf = open("World-Provinces/africa.dbf", "rb")

    shp = open("Africa/africa.shp", "rb")
    dbf = open("Africa/africa.dbf", "rb")
    sf = shapefile.Reader(shp=shp, dbf=dbf)

    # initializing arrays for data for Bokeh
    lats = []
    lons = []
    xs = []
    ys = []
    names = []

    # For each shape in the shapefile (each province)
    for shprec in sf.shapeRecords():
        names.append(shprec.record[2])
        # Not quite sure what's going on here but copied code that fixed the
        # strange lines issues
        lon, lat = map(list, zip(*shprec.shape.points))
        indices = shprec.shape.parts.tolist()
        lat = [lat[i:j] + [float('NaN')] for i, j in
               zip(indices, indices[1:]+[None])]
        lon = [lon[i:j] + [float('NaN')] for i, j in
               zip(indices, indices[1:]+[None])]
        lat = list(itertools.chain.from_iterable(lat))
        lon = list(itertools.chain.from_iterable(lon))
        x, y = zip(*map(lat_lon_to_web_mercator, lon, lat))

        # Eventually adding the list of lats for the shape to global lats list,
        # and list of lons for the shape to global lons list
        xs.append(x)
        ys.append(y)
        lats.append(lat)
        lons.append(lon)

    # Loading data into Bokeh
    return dict(
        x=xs,
        y=ys,
        lats=lats,
        lons=lons,
        name=names
    )


def load_protests():
    protests = pandas.read_csv('protests.csv')
    protests_wrong_long = protests[
        (protests.LONG == 'checked') | (protests.LONG.apply(safe_lt(-20)))
    ]
    protests = protests.drop(protests_wrong_long.index, axis='rows')
    lats = list(map(float, protests.LAT))
    lons = list(map(float, protests.LONG))
    x, y = zip(*map(lat_lon_to_web_mercator, lons, lats))
    return dict(
        x=x,
        y=y,
        lons=lons,
        lats=lats,
    )


def load_protest_reverse():
    try:
        return pandas.read_csv('protest-reverse-cache.csv')
    except RuntimeError:
        pass


def save_protest_reverse(data):
    keys = list(set(k for row in data for k in row.keys()))
    rows = [{k: row.get(k, None) for k in keys} for row in data]
    df = pandas.DataFrame({k: [r[k] for r in rows] for k in keys})
    df.to_csv('protest-reverse-cache.csv')


_special_names = {
    "Côte d'Ivoire": 'Cote d`Ivoire',
    'Congo, The Democratic Republic of the': 'Democratic Republic of Congo',
    'Congo': 'Congo-Brazzaville'
}


def sum_protests(protests, nations):
    counts = defaultdict(int)
    lons = protests['lons']
    lats = protests['lats']

    geo_data = load_protest_reverse()
    if geo_data is None:
        geo_data = []
        for i, (lat, lon) in enumerate(zip(lats, lons)):
            if not i % 10:
                print(f'{i}/{len(lats)}')
            try:
                rg = reverse_geo((lat, lon))[0]
            except IndexError:
                continue

            cname = pycountry.countries.get(alpha_2=rg['cc']).name
            if cname in _special_names:
                cname = _special_names[cname]
            counts[cname] += 1
            rg['countryname'] = cname
            geo_data.append(rg)

        save_protest_reverse(geo_data)
    else:
        counts = Counter(geo_data['countryname'])

    print(set(counts) - set(nations['name']))
    print(set(nations['name']) - set(counts))

    nations['protestcount'] = [counts[n] for n in nations['name']]
    nation_rank = sorted(set(counts.values()), reverse=True)
    nation_rank.append(0)
    nation_rank = {c: i for i, c in enumerate(nation_rank)}
    nation_rank = {n: nation_rank[counts[n]] for n in nations['name']}
    nations['rank'] = [nation_rank[n] for n in nations['name']]


def base_map():
    # TOOLS = "pan,wheel_zoom,reset,hover,save"
    TOOLS = "pan,wheel_zoom,reset,save"

    # Plot
    p = figure(
        title="Protests", tools=TOOLS,
        active_scroll='wheel_zoom',
        x_axis_location=None, y_axis_location=None,
        x_range=(-2300000, 6300000), y_range=(-4300000, 4600000),
        x_axis_type="mercator", y_axis_type="mercator",
        # tooltips=[
        #     ("Number of Protests", "@protestcount"),
        #     ("Rank Fraction", "@rank"),
        # ]
        )

    tile_provider = get_provider(STAMEN_TONER)
    tile_provider.url = 'http://tile.stamen.com/toner-lite/{Z}/{X}/{Y}@2x.png'
    p.add_tile(tile_provider)

    p.grid.grid_line_color = None
    p.hover.point_policy = "follow_mouse"

    return p


def patches(plot, patch_data):
    color_mapper = LinearColorMapper(palette=palette)
    plot.patches('x', 'y', source=patch_data,
                 fill_color={'field': 'rank', 'transform': color_mapper},
                 fill_alpha=0.4, line_color="lightblue", line_alpha=0.2,
                 line_width=2.0)
    return plot


def points(plot, point_data):
    glyph = Circle(x='x', y='y', fill_color="purple", fill_alpha=0.5,
                   line_color="gray", line_alpha=0.5, size=6)

    plot.add_glyph(ColumnDataSource(point_data), glyph)
    output_file("index.html")


if __name__ == "__main__":
    plot = base_map()

    protests = load_protests()
    nations = load_shape_records()
    sum_protests(protests, nations)

    patches(plot, nations)
    points(plot, protests)

    show(plot)

import itertools
import math
import csv

import shapefile
from shapely.geometry import Point, Polygon
import pandas
from bokeh.io import show, output_file
from bokeh.models import LogColorMapper, Circle, ColumnDataSource
from bokeh.palettes import Blues8 as palette
from bokeh.plotting import figure
from bokeh.tile_providers import CARTODBPOSITRON, get_provider

# This is the function for making the map of africa graph


def lat_lon_to_web_mercator(lon, lat):
    x = lon * 20037508.34 / 180
    y = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180)
    y = y * 20037508.34 / 180
    return x, y


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


def base_map():
    # TOOLS = "pan,wheel_zoom,reset,hover,save"
    TOOLS = "pan,wheel_zoom,reset,save"

    # Plot
    p = figure(
        title="Protests", tools=TOOLS,
        x_axis_location=None, y_axis_location=None,
        x_range=(-2000000, 6000000), y_range=(-1000000, 7000000),
        x_axis_type="mercator", y_axis_type="mercator",
        # tooltips=[
        #     ("Name", "@name"),
        # ]
        )

    tile_provider = get_provider(CARTODBPOSITRON)
    p.add_tile(tile_provider)

    p.grid.grid_line_color = None
    p.hover.point_policy = "follow_mouse"

    return p


def patches(plot, patch_data):
    color_mapper = LogColorMapper(palette=palette)
    plot.patches('x', 'y', source=patch_data,
                 fill_color={'field': 'rate', 'transform': color_mapper},
                 fill_alpha=0.4, line_color="white", line_width=0.5)
    return plot


def safe_lt(comp):
    def comp_func(val):
        try:
            return float(val) < comp
        except ValueError:
            return False
    return comp_func


def points(plot, point_data):
    glyph = Circle(x='x', y='y', fill_color="red", fill_alpha=0.8)

    plot.add_glyph(ColumnDataSource(point_data), glyph)
    output_file("index.html")


def sum_protests(protests, nations):
    xs = nations['x']
    ys = nations['y']

    p_xs = protests['x']
    p_ys = protests['y']

    nation_poly = [Polygon(zip(x[:-1], y)) for x, y in zip(xs, ys)]
    nation_counts = {n: 0 for n in nations['name']}
    for i, np in enumerate(nation_poly):
        count = 0
        for px, py in zip(p_xs, p_ys):
            if Point(px, py).within(np):
                count += 1
        nation_counts[nations['name'][i]] += 1

    nation_counts = [nation_counts[n] for n in nations['name']]
    nc_max = max(nation_counts)
    return [nc / nc_max for nc in nation_counts]


if __name__ == "__main__":
    plot = base_map()

    protests = load_protests()
    nations = load_shape_records()
    nations['rate'] = sum_protests(protests, nations)

    patches(plot, nations)
    points(plot, protests)
    show(plot)

import itertools
import math
import csv

import shapefile
import pandas
from bokeh.io import show, output_file
from bokeh.models import LogColorMapper, Circle, ColumnDataSource
from bokeh.palettes import Viridis6 as palette
from bokeh.plotting import figure

#This is the function for making the map of africa graph
def shp():
    #importing shp and dbf
    shp = open("World-Provinces/africa.shp", "rb")
    dbf = open("World-Provinces/africa.dbf", "rb")
    sf = shapefile.Reader(shp=shp, dbf=dbf)

    #initializing arrays for data for Bokeh
    lats = []
    lons = []
    rates = []
    names = []
    midx = 22
    midy = 5
    points = 0

    #For each shape in the shapefile (each province)
    for shprec in sf.shapeRecords():
        names.append(shprec.record[9])
        #Not quite sure what's going on here but copied code that fixed the strange lines issues
        lat, lon = map(list, zip(*shprec.shape.points))
        indices = shprec.shape.parts.tolist()
        lat = [lat[i:j] + [float('NaN')] for i, j in zip(indices, indices[1:]+[None])]
        lon = [lon[i:j] + [float('NaN')] for i, j in zip(indices, indices[1:]+[None])]
        lat = list(itertools.chain.from_iterable(lat))
        lon = list(itertools.chain.from_iterable(lon))
        #Eventually adding the list of lats for the shape to global lats list,
        #and list of lons for the shape to global lons list
        lats.append(lat)
        lons.append(lon)
        rates.append(math.sqrt((lat[0]-midx)**2 + (lon[0]-midy)**2))

    max = 0
    for i in rates:
        if i > max:
            max = i
    onerate = [i/max for i in rates]
    color_mapper = LogColorMapper(palette=palette)

    # Loading data into Bokeh
    data = dict(
        x=lats,
        y=lons,
        rate=onerate,
        name=names
    )

    TOOLS = "pan,wheel_zoom,reset,hover,save"

    # Plot
    p = figure(
        title="Protests", tools=TOOLS,
        x_axis_location=None, y_axis_location=None,
        tooltips=[
            ("Name", "@name"),
            # ("% Distance from Mid", "@rate%"),
            ("(Long, Lat)", "($x, $y)")
        ])

    p.grid.grid_line_color = None
    p.hover.point_policy = "follow_mouse"

    p.patches('x', 'y', source=data,
              fill_color={'field': 'rate', 'transform': color_mapper},
              fill_alpha=0.7, line_color="white", line_width=0.5)
    # show(p)
    return p


def safe_lt(comp):
    def comp_func(val):
        try:
            return float(val) < comp
        except ValueError:
            return False
    return comp_func


def points(plot):
    protests = pandas.read_csv('protests.csv')
    protests_wrong_long = protests[
        (protests.LONG == 'checked') | (protests.LONG.apply(safe_lt(-20)))
    ]
    protests = protests.drop(protests_wrong_long.index, axis='rows')
    lats = list(map(float, protests.LAT))
    lons = list(map(float, protests.LONG))
    data = ColumnDataSource(
        dict(lons=lons, lats=lats)
    )

    glyph = Circle(x="lons", y="lats", fill_color="red", fill_alpha=0.8)

    plot.add_glyph(data, glyph)
    output_file("index.html")
    show(plot)


if __name__ == "__main__":
    plot = shp()
    points(plot)

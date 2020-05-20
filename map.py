import math

from collections import defaultdict, Counter

import pycountry
from reverse_geocoder import search as reverse_geo

# from shapely.geometry import Point, Polygon
import pandas
import geopandas as gpd
import shapely
from bokeh.io import show, output_file
from bokeh.models import (
    LinearColorMapper, Circle, Patches, MultiPolygons,
    ColumnDataSource, GeoJSONDataSource,
    HoverTool, TapTool, OpenURL
)
from bokeh.palettes import Blues8 as palette
from bokeh.plotting import figure
from bokeh.tile_providers import (
    CARTODBPOSITRON_RETINA,
    get_provider
)

# This is the function for making the map of africa graph


def lat_lon_to_web_mercator(lon, lat):
    x = lon * 20037508.34 / 180
    y = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180)
    y = y * 20037508.34 / 180
    return x, y


def polygon_to_list(poly):
    shape = [list(poly.exterior.coords)]
    shape.extend(list(i.coords) for i in poly.interiors)
    return shape


def multipolygons_to_xs_ys(multipolygons):
    geometries = []
    for m in multipolygons:
        if isinstance(m, shapely.geometry.Polygon):
            m = [m]
        else:
            m = list(m)
        geometries.append(list(map(polygon_to_list, m)))

    geo_xs = [[[[x for x, y in ring_pairs]
                for ring_pairs in polygon]
               for polygon in multipolygon]
              for multipolygon in geometries]
    geo_ys = [[[[y for x, y in ring_pairs]
                for ring_pairs in polygon]
               for polygon in multipolygon]
              for multipolygon in geometries]
    return geo_xs, geo_ys


# If the world were a good place, this function would not be
# needed, and we could pass the geopandas dataframe straight
# to GeoJSONDataSource. That ALMOST works. But for some
# reason, no existing Bokeh glyph understands how to render
# patches with holes in them as represented by shapely Polygons.
# The closest thing is Bokeh's MultiPolygons glyph, but it
# doesn't accept shapely objects or geojson or anything
# like that. Wah wah. So instead we have to do this by hand.
def geodf_to_cds(geodf):
    geo_xs, geo_ys = multipolygons_to_xs_ys(geodf['geometry'])
    geodf = geodf.assign(xs=geo_xs, ys=geo_ys)
    return GeoJSONDataSource(geojson=geodf.to_json())


def safe_lt(comp):
    def comp_func(val):
        try:
            return float(val) < comp
        except ValueError:
            return False
    return comp_func


def load_shapefile():
    gdf = gpd.read_file('Africa/Africa.shp')
    gdf.crs = {'init': 'epsg:4326'}
    gdf = gdf.to_crs('EPSG:3857')
    gdf['admin'] = gdf['COUNTRY']
    print(gdf.head())
    return gdf


def load_geojson():
    gdf = gpd.read_file('Africa/africa-nations.json')
    gdf = gdf.to_crs('EPSG:3857')
    return gdf


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
    except FileNotFoundError:
        pass


def save_protest_reverse(data):
    keys = list(set(k for row in data for k in row.keys()))
    rows = [{k: row.get(k, None) for k in keys} for row in data]
    df = pandas.DataFrame({k: [r[k] for r in rows] for k in keys})
    df.to_csv('protest-reverse-cache.csv')


_special_names_shapefile = {
    "Côte d'Ivoire": 'Cote d`Ivoire',
    'Congo, The Democratic Republic of the': 'Democratic Republic of Congo',
    'Congo': 'Congo-Brazzaville'
}
_special_names_geojson = {
    'Congo': 'Republic of Congo',
    'Congo, The Democratic Republic of the':
        'Democratic Republic of the Congo',
    "Côte d'Ivoire": 'Ivory Coast'
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
            if cname in _special_names_geojson:
                cname = _special_names_geojson[cname]
            # if cname in _special_names_shapefile:
            #     cname = _special_names_shapefile[cname]
            counts[cname] += 1
            rg['countryname'] = cname
            geo_data.append(rg)

        save_protest_reverse(geo_data)
    else:
        counts = Counter(geo_data['countryname'])

    print(set(counts) - set(nations['admin']))
    print(set(nations['admin']) - set(counts))

    nations['protestcount'] = [counts[n] for n in nations['admin']]

    nation_rank = sorted(set(counts.values()), reverse=True)
    nation_rank.append(0)
    nation_rank = {c: i for i, c in enumerate(nation_rank)}
    nation_rank = {n: nation_rank[counts[n]] for n in nations['admin']}
    nations['rank'] = [nation_rank[n] for n in nations['admin']]


def base_map():
    TOOLS = "pan,wheel_zoom,tap,reset,save"

    # Plot
    p = figure(
        title="Protests", tools=TOOLS,
        active_scroll='wheel_zoom',
        x_axis_location=None, y_axis_location=None,
        x_range=(-2300000, 6300000), y_range=(-4300000, 4600000),
        x_axis_type="mercator", y_axis_type="mercator",
        )

    # tile_provider = get_provider(STAMEN_TONER)
    # tile_provider.url = ('http://tile.stamen.com/toner-lite/'
    #                      '{Z}/{X}/{Y}@2x.png')
    tile_provider = get_provider(CARTODBPOSITRON_RETINA)
    p.add_tile(tile_provider)
    p.grid.grid_line_color = None

    return p


def patches(plot, patch_data):
    color_mapper = LinearColorMapper(palette=palette)
    patches = MultiPolygons(
        xs='xs', ys='ys',
        fill_color={'field': 'rank', 'transform': color_mapper},
        fill_alpha=0.4, line_color="lightblue", line_alpha=0.2,
        line_width=2.0
    )
    hover_patches = MultiPolygons(
        xs='xs', ys='ys',
        fill_color={'field': 'rank', 'transform': color_mapper},
        fill_alpha=0.4, line_color="purple", line_alpha=0.8,
        line_width=2.0
    )
    render = plot.add_glyph(geodf_to_cds(patch_data),
                            patches,
                            hover_glyph=hover_patches,
                            selection_glyph=patches,
                            nonselection_glyph=patches)
    plot.add_tools(HoverTool(
        # tooltips=[
        #     ("Country", "@name"),
        #     ("Number of Protests", "@protestcount"),
        # ],
        tooltips=None,
        renderers=[render],
        point_policy="follow_mouse"
    ))
    tap = plot.select_one(TapTool)
    tap.renderers = [render]
    tap.callback = OpenURL(
        url='https://wikipedia.com/wiki/@name{safe}'
    )
    return plot


def points(plot, point_data):
    point = Circle(x='x', y='y', fill_color="purple", fill_alpha=0.5,
                   line_color="gray", line_alpha=0.5, size=6)
    plot.add_glyph(ColumnDataSource(point_data),
                   point)


if __name__ == "__main__":
    plot = base_map()

    protests = load_protests()
    # nations = load_shapefile()
    nations = load_geojson()
    sum_protests(protests, nations)

    patches(plot, nations)
    points(plot, protests)

    output_file("index.html")
    show(plot)

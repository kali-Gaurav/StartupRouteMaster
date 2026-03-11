import pandas as pd
import os

gtfs_dir = 'gtfs'
trips_df = pd.read_csv(os.path.join(gtfs_dir, 'trips.txt'))
shapes_df = pd.read_csv(os.path.join(gtfs_dir, 'shapes.txt'))

print("Trips shape_id count:", trips_df['shape_id'].nunique())
print("Shapes shape_id count:", shapes_df['shape_id'].nunique())

trips_shapes = set(trips_df['shape_id'].astype(str).unique())
shapes_shapes = set(shapes_df['shape_id'].astype(str).unique())

intersection = trips_shapes.intersection(shapes_shapes)
print("Intersection size:", len(intersection))

if len(intersection) > 0:
    print("Example common shape_id:", list(intersection)[0])
else:
    print("No common shape_ids found!")
    print("Trips example shape_ids:", list(trips_shapes)[:5])
    print("Shapes example shape_ids:", list(shapes_shapes)[:5])

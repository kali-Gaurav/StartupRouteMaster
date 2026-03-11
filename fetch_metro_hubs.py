import sqlite3
import os

db_path = 'backend/database/transit_graph.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

cities = ["Delhi", "Mumbai", "Chennai", "Kolkata", "Bangalore", "Hyderabad", "Pune", "Ahmedabad", "Lucknow", "Patna"]
query = "SELECT cluster_name, id FROM city_clusters WHERE cluster_name IN ({})".format(",".join(["?"] * len(cities)))
c.execute(query, cities)
print(c.fetchall())
conn.close()

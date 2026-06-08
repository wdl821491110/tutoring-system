import sqlite3
db = sqlite3.connect(r"C:\Users\jin\WorkBuddy\2026-06-04-21-31-16\tutoring-system\data\tutoring.db")
tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print("Tables:")
for t in tables:
    tname = t[0]
    count = db.execute("SELECT COUNT(*) FROM [" + tname + "]").fetchone()[0]
    cols = db.execute("PRAGMA table_info([" + tname + "])").fetchall()
    col_names = ", ".join([c[1] for c in cols])
    print("  [" + tname + "] (" + str(count) + " rows) cols: " + col_names)
db.close()

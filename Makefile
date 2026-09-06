.PHONY: data app league serve

# to get secrets for local dev:
# eval `cat ./data/.env | op inject`

# scrape CBS, ESPN, NFL projections and FantasyPros ADP, then aggregate them
data:
	python3 -m pip install -r ./data/requirements.txt && python3 ./data/main.py

# rebuild league/league_data.js for the draft room from the aggregated projections
league:
	python3 ./league/build.py

# open the draft room on http://localhost:8000
serve: league
	cd league && python3 -m http.server 8000

app:
	cd app && ./release.sh

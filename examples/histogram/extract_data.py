"""Regenerate datasets.json from the demo CSVs it lists (one column each).

    python examples/histogram/extract_data.py path/to/csv/folder
"""
import csv
import json
import sys
from pathlib import Path

DATASETS = [  # file, column, title, unit, decimals, note
    ('air_quality.csv', 'co2', 'CO2 in classrooms', 'ppm', 0,
     'Hourly CO2 in four rooms over a week: most hours are fresh, occupied hours make a long tail.'),
    ('air_quality.csv', 'temperature', 'Room temperature', 'degC', 2,
     'Same rooms: a narrow, roughly bell-shaped spread around 23.5 degC.'),
    ('air_quality.csv', 'light', 'Light level', 'lux', 1,
     'Dark hours and lit hours: two groups that few bins merge into one.'),
    ('h2_feed_in.csv', 'h2_einspeisung', 'Hydrogen share in the gas', '%', 2,
     'Invented scenario: about 0.3 % until the hydrogen arrives, then about 10 %. Zoom in with many bins.'),
    ('solar_day.csv', 'AC_POWER', 'Solar AC power (one day)', 'W', 0,
     'Every 15 minutes for a day: the night readings are exactly 0 W.'),
]


def main(data_dir: Path) -> None:
    out = []
    for file, col, title, unit, dec, note in DATASETS:
        with open(data_dir / file, encoding='utf-8') as fh:
            values = [round(float(r[col]), dec) for r in csv.DictReader(fh) if r[col] not in ('', None)]
        out.append({'title': title, 'unit': unit, 'note': note, 'source': f'{file}, column {col}',
                    'values': [int(v) if dec == 0 else v for v in values]})
        print(f'{title}: {len(values)} values')
    path = Path(__file__).with_name('datasets.json')
    path.write_text(json.dumps(out, separators=(',', ':')) + '\n', encoding='utf-8')
    print(path, path.stat().st_size, 'bytes')


if __name__ == '__main__':
    main(Path(sys.argv[1]))

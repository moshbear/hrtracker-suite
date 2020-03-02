# hrtracker-suite
Heart rate tracker data handler

This suite consists of a library portion (`lib/`) and a Flask-based web app.  
The library part has an optional requirement for `fitdecode` but is usable otherwise. 
The web app (`app.py`) requires the packages listed in `requirements.txt`.

The motivation behind this is dealing with Google Fit and heart point calculation but also
heart rate upload.

The library can be broken up into four parts, roughly following a map-filter-reduce pipeline with types:
* `consumers` -- these consume the pipeline and yield heart points and pnn-sgt files (`reducers`)
* `producers` -- these decode the files and produce a pipeline (`mappers`)
* `transformers` -- these filter the pipeline but can also transform one-to-many, like the splitter (`filters`)
* `types` -- these describe the types used by the pipeline

The app can be broken up into three parts:
* `/` -- the index
* `/points` -- the heart points calculator
* `/zipsplit` -- the hourly splits zipper

# Supported file formats
Supported input formats are: Garmin Fit and `com.pnn.android.sport_gear_tracker` (pnn-sgt)

Supported output formats are: pnn-sgt

To make use of pnn-sgt files, unzip to
`/sdcard/Android/data/com.pnn.android.sport_gear_tracker/files/user/detailed` (Android 10).

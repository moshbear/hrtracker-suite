# hrtracker-suite
#
# Copyright (c) 2020 Andrey V
# All rights reserved.
#
# This code is licensed under the 3-clause BSD License.
# See the LICENSE file at the root of this project.

# stdlib
from datetime import datetime
import hashlib
from io import BytesIO
import os
import re
import sys
from time import gmtime
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
# pypi
from flask import Flask, abort, render_template, request, send_file, url_for
import fitdecode
# local
# (this is a hack until app is split into a package and `import ..lib` can be
# done)
sys.path.insert(1, os.path.join(sys.path[0], '..'))
from lib import decode_stream, CannotDecodeFileException, \
                HRTrackerFilter, HRTrackerIdentityTransform, \
                HRTrackerSplitter, PnnSgtLogfile, HeartPointConfig


def points(files, hr_max = 220, pct_mod = 0.6, pct_hi = 0.7, pct_xhi = 0.85, \
           **kwargs):
    """
    Generate heart points for each passed tuple (`filehandle`, `filename`) in
    iterable `files`. A generator is returned that yields each successful 
    file.

    Configure the heart points calculator with params
    `hr_max`, `pct_mod`, `pct_hi`, `pct_xhi` . If `hr_min` is passed as an
    auxiliary kw arg, it is passed to a hr_min filter.
    """
    filter_kw = {k: kwargs[k] for k in {'hr_min'} & kwargs.keys()}
    if filter_kw:
        Filter = HRTrackerFilter
    else: 
        Filter = HRTrackerIdentityTransform
    point_config = HeartPointConfig(**{
        'hr_max': hr_max,
        'pct_mod': pct_mod, 'pct_hi': pct_hi, 'pct_xhi': pct_xhi
        })
    for (handle, name) in files:
        try:
            data = decode_stream(handle, name)
        except CannotDecodeFileException:
            continue
        yield point_config.heart_points(
                                 Filter(data, hr_max = hr_max, **filter_kw))

def zip_all_splits(filehandles, **kwargs):
    """
    Zip all hourly-split pnn sgt log files produced from decodable files in
    the iterable `filehandles` passed by handle. Pass additional arguments
    as needed to the filter, namely min and/or max heart rates.
    """
    hasher = hashlib.sha1()
    memory_file = BytesIO()
    filter_kw = {k: kwargs[k] for k in {'hr_min', 'hr_max'} & kwargs.keys()}
    if filter_kw:
        Filter = HRTrackerFilter
    else: 
        Filter = HRTrackerIdentityTransform
    with ZipFile(memory_file, 'w') as zf:
        for infile in filehandles:
            try:
                data = decode_stream(infile)
            except CannotDecodeFileException:
                continue
            for split in HRTrackerSplitter(Filter(data, **filter_kw)):
                sgt_file = PnnSgtLogfile(split)
                f_data = b''.join(l for l in sgt_file)
                data = ZipInfo(sgt_file.filename)
                # set timestamp to end_time of split
                data.date_time = gmtime(
                    sgt_file.start_time + sgt_file.elapsed_time
                )
                data.compress_type = ZIP_DEFLATED
                zf.writestr(data, f_data)
                hasher.update(f_data)
    memory_file.seek(0)
    return f'splits-{hasher.hexdigest()}.zip', memory_file

def stringify_start_time(t):
    return datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M:%S')

def stringify_end_time(t):
    return datetime.fromtimestamp(t).strftime('%H:%M:%S')

ranged_vals = {
    'cutoff': [ 0, 100 ],
    'hr':     [ 0, 220 ]
}
# range check the numeric inputs.
# abort 500 if called incorrectly or 400 if validation failed
# otherwise return the field value as int
def ranged(form, field, category):
    cat = ranged_vals.get(category)
    if not cat:
        abort(500, 'bad category for range check')
    val = form.get(field, None)
    if val is None:
        abort(400, f'expected input {field}')
    try:
        i_val = int(val)
        if i_val < cat[0] or i_val > cat[1]:
            raise ValueError(f'input {field} out of range')
        return i_val
    except (TypeError, ValueError):
        abort(400, f'bad value for input {field}')

pages = []

# browser sends empty filename if no file was selected
# check for that being false before handling the files
# with the exception class, the file-dependent parts can be wrapped in a
# `try -- except MissingFileException: pass` block
class MissingFileException(Exception):
    pass
def require_files(files):
    if len(files) and files[0].filename:
        return None
    else:
        raise MissingFileException()

app = Flask(__name__)
# 16 MB upload limit
app.config['MAX_CONTENT_LENGTH'] = 16 * 1 << 20

pages.append(('/points', 'Heart points calculator'))
@app.route('/points', methods=['POST', 'GET'])
def serve_points():
    cutoff_fields = [
        { 'field': 'v_mod', 'value': '60', 'descr': 'Moderate %HRmax cutoff' },
        { 'field': 'v_hi', 'value': '70', 'descr': 'Vigorous %HRmax cutoff' },
        { 'field': 'v_xhi', 'value': '85', \
          'descr': 'Extra-vigorous %HRmax cutoff' }
    ]
    template_kw = {
        'cutoff_fields': cutoff_fields,
        'ranged': ranged_vals
    }
    try:
        if request.method == 'POST':
            hr_max = ranged(request.form, 'hr_max', 'hr')
            kw_pts = { 'hr_max' : hr_max }
            for v in [ '_mod', '_hi', '_xhi' ]:
                kw_pts['pct' + v] = \
                    float(ranged(request.form, 'v' + v, 'cutoff')) / 100.0
            if request.form.get('hr_min_enable'):
                kw_pts['hr_min'] = ranged(request.form, 'hr_min', 'hr')
            # Process files
            files = request.files.getlist("files[]")
            require_files(files)

            points_v = points(((f.stream, f.filename) for f in files), **kw_pts)
            hpv_vals = sorted([_ for _ in points_v])

            cutoffs = HeartPointConfig.do_cutoffs(**kw_pts)

            template_kw['miscv'] = [
                [ 'Moderate', cutoffs[0] ],
                [ 'Vigorous', cutoffs[1] ],
                [ 'Extra-vigorous', cutoffs[2] ]
            ]

            # Evaluate a dots and commas expression to concatenate sources as
            # applicable for aggregate hp, cals, time range.
            if request.form.get('expr'):
                e = request.form['expr'][:EXPR_MAX_LEN]
                vals = set()
                n_hpv = len(hpv_vals)
                for e_dot in (d for d in re.split(r'\.+', e) if d):
                    try:
                        e_commas_u = \
                            (int(c) for c in re.split(',+', e_dot) if c)
                    except ValueError:
                        continue
                    # must use list instead of generator here because we need
                    # the last value (and also because iterated over twice
                    # (for now)
                    e_commas = [c for c in e_commas_u
                                if c > 0 and c <= n_hpv
                                and c not in vals and (vals.add(c) or True)]
                    first = e_commas[0]
                    last = e_commas[-1] if len(e_commas) > 1 else None
                    t0 = hpv_vals[first - 1].start
                    if last:
                        t1 = hpv_vals[last - 1].end
                    else:
                        t1 = hpv_vals[first - 1].end
                    nhp = sum(map(lambda e: hpv_vals[e - 1].points, e_commas))
                    ncals = \
                        sum(map(lambda e: int(hpv_vals[e - 1].cals), e_commas))
                    hpv_vals.append(HeartPointConfig.HeartPointObject(
                                    t0, t1, nhp, ncals))
            template_kw['hpv'] = (
                    (stringify_start_time(hp.start), stringify_end_time(hp.end),
                     hp.points, hp.cals) \
             for hp in hpv_vals)
    except MissingFileException:
        abort(400, 'No files were supplied')
    return render_template('points.htm', **template_kw)

pages.append(('/zipsplit', 'Save hourly splits to zip'))
@app.route('/zipsplit', methods=['POST', 'GET'])
def serve_zipsplit():
    template_kw = {
        'ranged': ranged_vals
    }
    try:
        if request.method == 'POST':
            kw_zipper = {}
            if request.form.get('hr_min_enable'):
                hr_min = ranged(request.form, 'hr_min', 'hr')
                kw_zipper['hr_min'] = hr_min
            # Process files
            files = request.files.getlist("files[]")
            require_files(files)
            zip_name, zip_data = \
                zip_all_splits((f.stream for f in files), **kw_zipper)
            return send_file(zip_data, mimetype='application/zip',
                             as_attachment = True,
                             attachment_filename = zip_name)
    except MissingFileException:
        abort(400, 'No files were supplied')
    return render_template('zipsplit.htm', **template_kw)

@app.route('/')
def serve_index():
    return render_template('index.htm', pages = pages)


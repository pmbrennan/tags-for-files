#!/usr/bin/env python
# coding: utf-8

import argparse
import datetime
import operator
import os
import pickle
import pprint
import shutil
import sys
from os.path import basename
from os.path import exists

import PySimpleGUI as sg
import tinytag
from tinytag import TinyTag

# **********************************************************************
# Parse arguments and set up primary data structures
parser = argparse.ArgumentParser('TagsForFiles')
parser.add_argument('base',
                    help='Base directory for data',
                    default=os.getcwd(),
                    nargs='?',
                    )
args = parser.parse_args()
main_data_directory = args.base
main_data_directory = os.path.expanduser(os.path.expandvars(main_data_directory))
sys.path.append(main_data_directory)

# Where to store the durable database
pickle_file_path = os.path.join(main_data_directory, "tags4files.pickle")
pickle_file_path = os.path.abspath(pickle_file_path)
print(f'pickle_file_path = {pickle_file_path}')

# Where to store the compatible database
text_file_path = os.path.join(main_data_directory, "tags.txt")
text_file_path = os.path.abspath(text_file_path)
print(f'text_file_path = {text_file_path}')


# **********************************************************************
# Top-level internal data structure
def create_t4f_data():
    """Create and return the base data structure"""
    data = {
        'files': [],  # List of file objects with their respective tags
        'tags': set(),  # Set of unique tags
    }
    return data


# Primary data structure
_tags4files = create_t4f_data()


def save_t4f_data_to_pickle(t4f_data=None, filename=None):
    """Write data to the pickle file"""
    if t4f_data is None:
        t4f_data = _tags4files
    if filename is None:
        filename = pickle_file_path
    pickle_file = open(filename, "wb")
    pickle.dump(t4f_data, pickle_file)
    pickle_file.close()
    pass


def save():
    save_t4f_data_to_pickle()
    pass


def load_t4f_data_from_pickle(filename=None):
    """Read data from the pickle file"""
    if filename is None:
        filename = pickle_file_path
    pickle_file = open(filename, "rb")
    t4f_data = pickle.load(pickle_file)
    pickle_file.close()
    return t4f_data


def create_or_load_t4f_data_from_pickle(filename=None):
    """Load the data file if it exists, otherwise create it and save it out."""
    if filename is None:
        filename = pickle_file_path
    file_exists = exists(filename)
    if file_exists:
        t4f_data = load_t4f_data_from_pickle(filename)
    else:
        t4f_data = create_t4f_data()
        save_t4f_data_to_pickle(t4f_data, filename)
    return t4f_data


# Data parser, adds new data to an existing database
def get_or_build_file_object(file_list, path):
    """If the file record already exists, return it, otherwise create a new record and append it."""
    for f in file_list:
        if f['path'] == path:
            return f
    # We didn't find it; therefore, create it.
    f = {
        'id': len(file_list),
        'path': path,
        'exists': exists(path),
        'tags': set(),
        'comments': [],
    }
    if not f['exists']:
        print(f"WARNING: Could not find file '{path}'")
    file_list.append(f)
    return f


def get_variables_from_file_object(file_object):
    """
    Find all the tags in a file object in the form "<key>=<value>" and build a dict
    which represents the mapping.
    """
    # TODO Make sure to scrub tags for degenerate values e.g. '=s', 'x=y=z' etc.
    variables = {}
    for t in file_object['tags']:
        if t.find('=') > 0:
            (k, v) = t.split('=')
            variables[k] = v
    return variables


def import_text_data(t4f_data,
                     text_data):  # list of lines
    """Add data from text to the base data structure"""
    want_path_name = True  # The next non-blank line will be interpreted as a file path
    want_tags = False  # The next non-blank line will be interpreted as a set of tags
    record = None

    for line in text_data:
        stripped_line = line.strip()

        if len(stripped_line) == 0:
            want_path_name = True
            want_tags = False
        elif stripped_line[0] == '#':
            if want_tags:
                record['comments'].append(stripped_line)
            pass
        else:
            if want_path_name:
                record = get_or_build_file_object(t4f_data['files'], stripped_line)
                want_path_name = False
                want_tags = True
            elif want_tags:
                tags_list = [t.strip() for t in stripped_line.split()]
                record['tags'].update(tags_list)
                t4f_data['tags'].update(tags_list)
        pass


def import_text_data_from_file(t4f_data,
                               filename):
    """Add data from a text file to the base data structure"""
    file = open(filename, encoding='utf-8')
    data = file.readlines()
    file.close()
    import_text_data(t4f_data, data)


def build_tagged_files_map(t4f, only_existing=False):
    """
    Given a tag4files structure as defined by:
    - 'tags' a set of tags, each a string
    - 'files' a list of structs for each file:
      - 'id' a numeric id
      - 'path' filepath,
      - 'exists' boolean, does the pathname correspond to an existing file,
      - 'tags' a set of tags for this file
      - 'comments' a list of strings, each preceded by '#'

    Return a map, where each key is a tag and each value is a set of filenames
    corresponding to files which have the key tag.

    If only_existing is set to True, then only return existing files.

    """
    m = {}
    for t in t4f['tags']:
        m[t] = set()
    for f in t4f['files']:
        if only_existing and not f['exists']:
            continue
        for t in f['tags']:
            m[t].add(f['path'])
    return m


def get_matching_tagged_files(tags, t4f=None, only_existing=False):
    """Return a set of files which match all the given tags"""
    if tags is None or len(tags) == 0:
        return []
    if t4f is None:
        t4f = _tags4files
    tagged_files_map = build_tagged_files_map(t4f, only_existing)

    try:
        sets = [tagged_files_map[t] for t in tags]
    except KeyError:
        return []

    first = True
    out = None
    for s in sets:
        if first:
            out = s
            first = False
        else:
            out = out.intersection(s)
    return out


def get_tags_from_files(files, t4f=None):
    """Return a list of tags which match the given files"""
    tags = set()
    if t4f is None:
        t4f = _tags4files
    for f in t4f['files']:
        if f['path'] in files:
            for tag in f['tags']:
                tags.add(tag)
    return list(tags)


def get_missing_files(t4f=None):
    """Return a list of files which are in the index but can't be found on the filesystem."""
    if t4f is None:
        t4f = _tags4files
    out = []
    for f in t4f['files']:
        if not f['exists']:
            out.append(f['path'])
        pass
    return out


def prune(t4f=None):
    """Remove files which are in the index but can't be found on the filesystem."""
    if t4f is None:
        t4f = _tags4files
    new_files = []
    not_found = 0
    for f in t4f['files']:
        if f['exists']:
            new_files.append(f)
        else:
            not_found += 1
    t4f['files'] = new_files
    if not_found > 0:
        print(f"{not_found} files pruned. Export and/or save recommended.")
    pass


def paragraph_wrap(text_to_reflow, columns):
    """
    Restrict a string to <columns> width. Add newlines as necessary.
    Assumes there is only one space between tokens.
    """
    sub_strings = text_to_reflow.split(' ')
    out_list = []
    build = ''
    for i in range(0, len(sub_strings)):
        if len(sub_strings[i]) == 0:
            continue
        if len(build) + len(sub_strings[i]) < columns:
            build += ' ' + sub_strings[i].strip()
            pass
        elif build == '':
            out_list.append(' ' + sub_strings[i].strip())
            pass
        else:
            out_list.append(build.strip())
            build = sub_strings[i]
            pass
        pass
    if len(build) > 0:
        out_list.append(build.strip())
    return "\n".join(out_list)


def write_to_file(t4f, filename):
    """Write the base data structure out to a text file"""
    t4f['files'].sort(key=lambda r: r['path'])
    file = open(filename, "w", encoding="utf-8")

    for f in t4f['files']:
        print(f['path'], file=file)
        for c in f['comments']:
            print(c, file=file)
        tags = f['tags']
        tags_list = list(tags)
        tags_list.sort()

        p = paragraph_wrap(' '.join(tags_list), 72)

        print(p, file=file)
        print('', file=file)

    file.close()


def find_duplicated_filenames(t4f_data=None):
    """
    Returns a list of filenames which are found in
    more than one pathname in the base data.
    """
    if t4f_data is None:
        t4f_data = _tags4files
    out = []
    base_names = set()
    for f in t4f_data['files']:
        b = basename(f['path'])
        if b in base_names:
            out.append(f['path'])
        else:
            base_names.add(b)
    return out


def ends_with(filename, extensions=None):
    if extensions is None:
        extensions = []
    for ext in extensions:
        if filename.endswith(ext):
            return True
        pass
    return False


video_extensions = [
    'wmv',
    'mp4',
    'mkv',
    'mov',
    'mpg',
    'avi',
    'm4v',
    'MPG',
    'MP4',
    'MOV',
    'mpeg'
]

audio_extensions = [
    'ogg',
    'wav',
    'mp3'
]


def find_untracked(extensions=None, t4f_data=None):
    """Find files which aren't accounted for yet."""
    if t4f_data is None:
        t4f_data = _tags4files
    if extensions is None:
        extensions = audio_extensions
    untracked_files = []
    known_files = set()

    found_extensions = set()

    for f in t4f_data['files']:
        known_files.add(f['path'])

    gen = os.walk(main_data_directory)
    for rec in gen:
        dir_path = rec[0]
        dir_names = rec[1]
        filenames = rec[2]
        for filename in filenames:
            path_tuple = os.path.splitext(filename)
            if len(path_tuple[1]) > 0:
                ext = path_tuple[1][1:]
                if ext not in extensions:
                    found_extensions.add(ext)
                    pass
                pass

            if not ends_with(filename, extensions):
                continue

            path = os.path.join(dir_path, filename)
            if path not in known_files:
                untracked_files.append(path)
                pass
            pass
        pass
    filename = make_time_stamped_file_name('untracked', 'm3u')
    f = open(filename, "w", encoding="utf-8")
    print('\n\n'.join(untracked_files), file=f)
    f.close()
    print(f'Wrote {len(untracked_files)} untracked files to {filename}')
    print(f'Other extensions = {found_extensions}')


def make_time_stamped_file_name(prefix, suffix):
    """Make a filename which contains the time and date of creation"""
    if suffix is None:
        suffix = 'm3u'
    now = datetime.datetime.now()
    elements = [
        prefix,
        f'{now.year}',
        f'{now.month:02d}',
        f'{now.day:02d}',
        f'{now.hour:02d}',
        f'{now.minute:02d}',
        f'{now.second:02d}',
    ]
    file_name = f"{'-'.join(elements)}.{suffix}"
    return os.path.join(main_data_directory, file_name)


def make_m3u(tags, t4f_data=None):
    """
    Make a m3u playlist of all the files which contain all the passed
    tags.
    """
    if t4f_data is None:
        t4f_data = _tags4files
    filename = make_time_stamped_file_name('playlist', 'm3u')
    f = open(filename, "w", encoding="utf-8")
    filelist = get_matching_tagged_files(tags, t4f_data, only_existing=True)
    print('\n'.join(filelist), file=f)
    f.close()
    print(f'Wrote {len(filelist)} files to {filename}')


def score_entries(entries, tag_values=None):
    out = []
    for entry in entries:
        score = 0
        for tag in entry['tags']:
            if tag_values is not None and tag in tag_values:
                score += tag_values[tag]
            else:
                score += 1
                pass
            pass
        entry['score'] = score
        out.append(entry)
        pass
    return out


def top_rated_m3u(limit=0, t4f_data=None):
    if t4f_data is None:
        t4f_data = _tags4files
    scored_entries = score_entries(t4f_data['files'])
    sorted_entries = sorted(scored_entries, key=operator.itemgetter('score'), reverse=True)
    if limit > 0:
        sorted_entries = sorted_entries[0:limit]
    file_list = [e['path'] for e in sorted_entries]

    filename = make_time_stamped_file_name('playlist', 'm3u')

    f = open(filename, "w", encoding="utf-8")
    print('\n'.join(file_list), file=f)
    f.close()
    print(f'Wrote to {filename}')


def export(t4f_data=None):
    """Write tags4files out to a .txt file"""
    if t4f_data is None:
        t4f_data = _tags4files

    now_file = make_time_stamped_file_name('tags', 'txt')

    write_to_file(t4f_data, now_file)
    print(f'Results written to {now_file}')
    return now_file


def find_matching_files_for_text_term(term, t4f_data=None):
    """Return a list of file structs which match term (case-insensitive)"""
    if t4f_data is None:
        t4f_data = _tags4files
    out = []
    t = term.lower()
    for file in t4f_data['files']:
        p = file['path'].lower()
        if t in p:
            out.append(file)
        pass
    return out


def find_matching_tags_for_text_term(term, t4f_data=None):
    """Return a list of tags which match term (case-insensitive)"""
    if t4f_data is None:
        t4f_data = _tags4files
    out = []
    t = term.lower()
    for tag in t4f_data['tags']:
        tag = tag.lower()
        if t in tag:
            out.append(tag)
        pass
    return out


def write_m3u_file(path_list, prefix):
    m3u_filename = make_time_stamped_file_name(prefix, 'm3u')
    f = open(m3u_filename, "w", encoding="utf-8")
    print('\n'.join(path_list), file=f)
    f.close()
    return m3u_filename
    pass


def matching_m3u(term, t4f_data=None):
    """Writes out a m3u which matches a term (case-insensitive)"""
    if t4f_data is None:
        t4f_data = _tags4files
    files = find_matching_files_for_text_term(term, t4f_data)
    paths = [f['path'] for f in files]
    if len(paths) > 0:
        filename = write_m3u_file(paths, 'playlist')
        print(f'Wrote {len(paths)} files to {filename}')
    else:
        print('No records found.')
    pass


def add_tag(files, tag):
    """Apply the given tag to each file in files."""
    for file in files:
        file['tags'].add(tag)
        pass
    pass


def transform_to_tag(text):
    to_remove = '/,()\'\"!&%;^$#@<>{}[]\\|?*~`'  # These characters have no business in a tag

    tag = text.lower().translate({ord(i): None for i in to_remove})
    tag = tag.replace(' - ', '-') \
        .replace('    ', '-') \
        .replace('   ', '-') \
        .replace('  ', '-') \
        .replace(' ', '-') \
        .replace('-----', '-') \
        .replace('----', '-') \
        .replace('---', '-') \
        .replace('--', '-')
    return tag


def extract_tags(pathname):
    out = set()
    try:
        tag = TinyTag.get(pathname)
    except tinytag.tinytag.TinyTagException as e:
        print(f'WARNING: exception for {pathname}:')
        print(e)
        return out

    if tag.artist is not None and len(tag.artist) > 0:
        out.add('artist=' + transform_to_tag(tag.artist))
    if tag.year is not None and len(tag.year) > 0:
        out.add('year=' + transform_to_tag(tag.year))
    if tag.album is not None and len(tag.album) > 0:
        out.add('album=' + transform_to_tag(tag.album))
    if tag.title is not None and len(tag.title) > 0:
        out.add('title=' + transform_to_tag(tag.title))
    return out


def extract_all_tags(t4f=None):
    if t4f is None:
        t4f = _tags4files
    for f in t4f['files']:
        if f['exists']:
            new_tags = extract_tags(f['path'])
            f['tags'].update(new_tags)


def clean_all_tags(t4f=None):
    if t4f is None:
        t4f = _tags4files
    for f in t4f['files']:
        old_tags = f['tags']
        new_tags = set()
        for t in old_tags:
            new_tags.add(transform_to_tag(t))
            pass
        f['tags'] = new_tags
        pass
    pass


def replace_tag(target, replace, t4f=None):
    if t4f is None:
        t4f = _tags4files
    for f in t4f['files']:
        if target in f['tags']:
            f['tags'].remove(target)
            f['tags'].add(replace)
            pass
        pass
    if target in t4f['tags']:
        t4f['tags'].remove(target)
        t4f['tags'].add(replace)
        pass
    pass


def count_tags(t4f=None):
    if t4f is None:
        t4f = _tags4files
    tag_counts = {}
    for f in t4f['files']:
        for t in f['tags']:
            if t not in tag_counts:
                tag_counts[t] = 0
                pass
            tag_counts[t] += 1
            pass
        pass
    out = sorted(tag_counts.items(), key=lambda i: i[1], reverse=True)
    return out


def move_if_tagged(ttag, ddir, t4f=None):
    """
    Find any files marked with the tag specified in ttag, and move them to a special
    directory as specified in ddir under the current working directory.
    """
    if t4f is None:
        t4f = _tags4files
    to_move = []
    n_moved = 0
    dest_folder = os.path.join(main_data_directory, ddir)
    if not os.path.exists(dest_folder):
        os.mkdir(dest_folder)
        pass
    for f in t4f['files']:
        if ttag in f['tags']:
            file_dir = os.path.dirname(f['path']).split('\\')[-1]
            if file_dir != ddir:
                to_move.append(f)
                pass
            pass
        pass
    for f in to_move:
        file_name = os.path.split(f['path'])[1]
        src = f['path']
        dst = os.path.join(dest_folder, file_name)

        if os.path.exists(dst):
            print(f'I wanted to move `{src}` to `{dst}`, but `{dst}` already exists!')
        else:
            shutil.move(src, dst)
            print(f'Moved `{src}` to `{dst}`')
            n_moved += 1
            f['path'] = dst
            pass
        pass
    print(f'Moved {n_moved} files to {ddir}, out of {len(to_move)} requested.')
    if n_moved > 0:
        print('export() and/or save() recommended.')
        pass
    pass


def delete(t4f=None):
    """
    Find any files marked with the tag 'to-delete' and move them to a special
    directory called '.trash'.
    """
    if t4f is None:
        t4f = _tags4files
    move_if_tagged('to-delete', '.trash', t4f)
    pass


def favorite(t4f=None):
    """
    Find any files marked with the tag 'move-to-favorites' and move them to a special
    directory called '.favorites'.
    """
    if t4f is None:
        t4f = _tags4files
    move_if_tagged('move-to-favorites', '.favorites', t4f)
    pass


def archive(t4f=None):
    """
    Find any files marked with the tag 'to-archive' and move them to a special
    directory called '.archive'.
    """
    if t4f is None:
        t4f = _tags4files
    move_if_tagged('to-archive', '.archive', t4f)
    pass


# Data format is as follows:
# A record consists of a sequence of non-blank lines.
# - The first line contains the file path
# - An optional number of lines after the path contains file comments,
#   indicated by the presence of a '#' as the first character of the line.
# - Every subsequent non-blank line contains tags, each separated by 1 or more spaces.
# - A tag in the form '<k>=<v>' where k and v are both valid strings is considered
#   to be a variable, with the name k and the value v.
# - Complete records are separated by one or more blank lines.
import_text_data_from_file(_tags4files, text_file_path)
pp = pprint.PrettyPrinter(indent=2)

print()
print(f"Read {len(_tags4files['files'])} files.")

print()
print(f"Read {len(_tags4files['tags'])} tags.")

print()
missing_files = get_missing_files(_tags4files)
print(f'{len(missing_files)} Missing files.')
# pp.pprint(get_missing_files(_tags4files))

print()
possible_dupes = find_duplicated_filenames()
print(f'{len(possible_dupes)} Possibly-duplicated files.')
# pp.pprint(possible_dupes)

print()

export()

find_untracked(video_extensions)

# number_top = 20
# print(f'Top {number_top} tags:')
# pp.pprint(sorted(count_tags(), key=lambda x: x[1], reverse=True)[0:number_top])
# print()

print('Use `export()` to write to a text file tags list')
print('Use `save() to write to a pickle file')
print('Use `find_matching(term) to find file names which match a search term')
print('Use `get_matching_tagged_files(tags)` to get a list of files which match tags')
print('Use `make_m3u(tags)` to make a playlist of the given tags')
print('Use `matching_m3u(term)` to make a playlist matching the given term')
print('Use `top_rated_m3u()` to make a playlist of the top-rated tracks')
print('Use `find_untracked(extensions)` to make a list of untracked files.')
print('Use `get_missing_files()` to find files which are indexed but not on the filesystem.')
print('Use `extract_all_tags()` to pull tags out of embedded metadata.')
print('Use `delete()` to move files marked with the `to-delete` tag to `.trash`')
print('Use `favorite()` to move files marked with the `move-to-favorites` tag to `.favorites`')
print('Use `archive()` to move files marked with the `to-archive` tag to `.archive`')

# PySimpleGui core
files_list = [f['path'] for f in _tags4files['files']]
tag_list = list(_tags4files['tags'])
tag_list.sort()
layout = [
    [sg.Text(f'Base directory: {main_data_directory} | {len(files_list)} files | {len(tag_list)} tags')],
    [sg.HorizontalSeparator()],

    [sg.Column([[sg.Text('ALL FILES:'),
                 sg.DropDown(values=['Alpha', 'Selected'],
                             default_value='Alpha',
                             enable_events=True,
                             readonly=True,
                             size=30, key='FILES-DROPDOWN-SORT')],
                [sg.Listbox(values=files_list,
                            size=(100, 20),
                            key='-FILES-LISTBOX-',
                            select_mode=sg.LISTBOX_SELECT_MODE_EXTENDED,
                            enable_events=True,
                            horizontal_scroll=True)
                 ]]),
     sg.Column([[sg.Text('ALL TAGS:'),
                 sg.DropDown(values=['Alpha', 'Frequency', 'Selected'],
                             default_value='Alpha',
                             enable_events=True,
                             readonly=True,
                             size=30, key='TAGS-DROPDOWN-SORT')],
                [sg.Listbox(values=tag_list,
                            size=(45, 20),
                            key='-TAGS-LISTBOX-',
                            select_mode=sg.LISTBOX_SELECT_MODE_EXTENDED,
                            enable_events=True,
                            horizontal_scroll=True)]])],

    [sg.Text(size=(80, 1), key='-SELECT-STATUS-')],
    [sg.InputText('', size=(80, 1), key='FIND-ENTRY', enable_events=True), sg.Button('Find', key='FIND-BUTTON')],
    [
        sg.Button('Clear files selection', key='-CLEAR-FILES-',
                  tooltip='Unselect all files'),
        sg.Button('Clear tags selection', key='-CLEAR-TAGS-',
                  tooltip='Unselect all tags'),
        sg.Button('Files from Tags', key='SELECT-FILES-FROM-TAGS',
                  tooltip='Select files which match all of the selected tags'),
        sg.Button('Tags from Files', key='SELECT-TAGS-FROM-FILES',
                  tooltip='Select all tags which can be found in any of the selected files'),
        sg.DropDown(values=['Replace', 'Expand'], default_value='Replace', readonly=True,
                    tooltip='Replace current selection or expand it', size=30,
                    key='REPLACE-OR-EXPAND-SELECTION')
    ],
    [
        sg.Button('Export entire file list', key='EXPORT-BUTTON', ),
        sg.Button('Make a playlist of selected files', key='PLAYLIST-BUTTON', ),
        sg.Text(size=(90, 1), key='FILE_OP_STATUS'),
    ],
    [sg.HorizontalSeparator()],
    [sg.Button('Quit')]
]


def select_files_from_tags(window):
    tags_list = window['-TAGS-LISTBOX-'].get()
    file_list = list(get_matching_tagged_files(tags_list))
    if file_list is None:
        file_list = []
    if window['REPLACE-OR-EXPAND-SELECTION'].get() == 'Expand':
        for f in window['-FILES-LISTBOX-'].get():
            if f not in file_list:
                file_list.append(f)
    window['-FILES-LISTBOX-'].set_value(file_list)


def select_tags_from_files(window):
    files_list = window['-FILES-LISTBOX-'].get()
    tags_list = list(get_tags_from_files(files_list))
    if tags_list is None:
        tags_list = []
    if window['REPLACE-OR-EXPAND-SELECTION'].get() == 'Expand':
        for t in window['-TAGS-LISTBOX-'].get():
            if t not in tags_list:
                tags_list.append(t)
    window['-TAGS-LISTBOX-'].set_value(tags_list)


def update_selection_display(window):
    n_selected_files = len(window['-FILES-LISTBOX-'].get())
    n_selected_tags = len(window['-TAGS-LISTBOX-'].get())
    window['-SELECT-STATUS-'].update(f'Selected: {n_selected_files} files | {n_selected_tags} tags')


def update_tags_sort_order(window):
    sort_order = window['TAGS-DROPDOWN-SORT'].get()
    selected = window['-TAGS-LISTBOX-'].get()
    tag_list = []

    if sort_order is 'Alpha':
        tag_list = list(_tags4files['tags'])
        tag_list.sort()
    elif sort_order is 'Selected':
        tag_list = list(_tags4files['tags'])
        augmented_tag_list = [(t, t in selected) for t in tag_list]
        sorted_tag_list = sorted(augmented_tag_list, key=lambda x: f' {x[0]}' if x[1] else x[0])
        tag_list = [t[0] for t in sorted_tag_list]
    elif sort_order is 'Frequency':
        tag_list = [item[0] for item in count_tags()]

    window['-TAGS-LISTBOX-'].update(tag_list)
    window['-TAGS-LISTBOX-'].set_value(selected)
    update_selection_display(window)


def update_files_sort_order(window):
    sort_order = window['FILES-DROPDOWN-SORT'].get()
    selected = window['-FILES-LISTBOX-'].get()
    file_list = []
    if sort_order is 'Alpha':
        file_list = [f['path'] for f in _tags4files['files']]
        file_list.sort()
    elif sort_order is 'Selected':
        file_list = [f['path'] for f in _tags4files['files']]
        augmented_file_list = [(f, f in selected) for f in file_list]
        sorted_file_list = sorted(augmented_file_list, key=lambda x: f' {x[0]}' if x[1] else x[0])
        file_list = [f[0] for f in sorted_file_list]
    window['-FILES-LISTBOX-'].update(file_list)
    window['-FILES-LISTBOX-'].set_value(selected)
    update_selection_display(window)


def do_export(window):
    window['FILE_OP_STATUS'].update('Writing export file')
    file_name = export()
    window['FILE_OP_STATUS'].update(f'Wrote {file_name}')


def do_make_playlist(window):
    window['FILE_OP_STATUS'].update('Writing m3u file')
    files_list = window['-FILES-LISTBOX-'].get()
    filename = make_time_stamped_file_name('playlist', 'm3u')
    f = open(filename, 'w', encoding='utf-8')
    print('\n'.join(files_list), file=f)
    f.close()
    status_message = f'Wrote {len(files_list)} files to {filename}'
    print(status_message)
    window['FILE_OP_STATUS'].update(status_message)


def do_find(window):
    find_text = window['FIND-ENTRY'].get()
    if len(find_text) == 0:
        window['-TAGS-LISTBOX-'].set_value([])
        window['-FILES-LISTBOX-'].set_value([])
    else:
        file_matches = find_matching_files_for_text_term(find_text)
        window['-FILES-LISTBOX-'].set_value([f['path'] for f in file_matches])
        tag_matches = find_matching_tags_for_text_term(find_text)
        window['-TAGS-LISTBOX-'].set_value(tag_matches)
    update_selection_display(window)


# Create the window
window = sg.Window('Tags For Files', layout)

# EVENT LOOP:
# Display and interact with the Window using an Event Loop
while True:
    event, values = window.read()
    print(event,values)
    # See if user wants to quit or window was closed
    if event == sg.WINDOW_CLOSED or event == 'Quit':
        break
    elif event == '-FILES-LISTBOX-' or event == '-TAGS-LISTBOX-':
        update_selection_display(window)
    elif event == '-CLEAR-FILES-':
        window['-FILES-LISTBOX-'].set_value([])
        update_selection_display(window)
    elif event == '-CLEAR-TAGS-':
        window['-TAGS-LISTBOX-'].set_value([])
        update_selection_display(window)
    elif event == 'SELECT-FILES-FROM-TAGS':
        select_files_from_tags(window)
        update_selection_display(window)
    elif event == 'SELECT-TAGS-FROM-FILES':
        select_tags_from_files(window)
        update_selection_display(window)
    elif event == 'TAGS-DROPDOWN-SORT':
        update_tags_sort_order(window)
    elif event == 'FILES-DROPDOWN-SORT':
        update_files_sort_order(window)
    elif event == 'EXPORT-BUTTON':
        do_export(window)
    elif event == 'PLAYLIST-BUTTON':
        do_make_playlist(window)
    elif event == 'FIND-BUTTON':
        do_find(window)

# Finish up by removing from the screen
window.close()

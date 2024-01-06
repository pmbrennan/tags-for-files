#!/usr/bin/env python
# coding: utf-8

import argparse
import datetime
import os
import pprint
import shutil
import sys
from os.path import basename
from os.path import exists

import PySimpleGUI as sg
import tinytag
from tinytag import TinyTag


# ######################################################################
# FileRecord
# ######################################################################
class FileRecord:
    def __init__(self, file_id, path, file_exists):
        self.id = file_id
        self.path = path
        self.file_exists = file_exists
        self.comments = []
        self.tags = set()

    def get_variables(self):
        """
        Find all the tags in a file object in the form "<key>=<value>" and build a dict
        which represents the mapping.
        """
        variables = {}
        for t in self.tags:
            if t.find('=') > 0:
                parsed = t.split('=')
                if len(parsed) != 2:
                    continue
                if parsed[0] is None or len(parsed[0]) == 0:
                    continue
                if parsed[1] is None or len(parsed[1]) == 0:
                    continue
                variables[parsed[0]] = parsed[1]
        return variables


# ######################################################################
# TagsForFiles
# ######################################################################
class TagsForFiles:
    def __init__(self):
        self.tags = set()
        self.file_records = []
        pass

    def add_path(self, path):
        """
        If the file record already exists, return it, otherwise create a new record and append it.
        """
        for f in self.file_records:
            if f.path == path:
                return f
        # We didn't find it; therefore, create it.
        f = FileRecord(file_id=len(self.file_records), path=path, file_exists=exists(path))
        if not f.file_exists:
            print(f"WARNING: Could not find file '{path}'")
        self.file_records.append(f)
        return f

    def import_text_data(self,
                         text_data):  # list of lines
        """
        Add data from lines of text to the base data structure
        """
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
                    record.comments.append(stripped_line)
                pass
            else:
                if want_path_name:
                    record = self.add_path(stripped_line)
                    want_path_name = False
                    want_tags = True
                elif want_tags:
                    tags_list = [t.strip() for t in stripped_line.split()]
                    record.tags.update(tags_list)
                    self.tags.update(tags_list)
            pass

    def import_text_data_from_file(self,
                                   filename):
        """
        Add data from a text file to the base data structure
        TODO: Parse the file directly instead of reading lines into a buffer and then parsing the buffer.
        """
        file = open(filename, encoding='utf-8')
        data = file.readlines()
        file.close()
        self.import_text_data(data)

    def build_tagged_files_map(self, only_existing=False):
        """
        Given a tag4files structure as defined by:
        - 'tags' a set of tags, each a string
        - 'file_records' a list of structs for each file:
          - 'file_id' a numeric file_id
          - 'path' filepath,
          - 'file_exists' boolean, does the pathname correspond to an existing file,
          - 'tags' a set of tags for this file
          - 'comments' a list of strings, each preceded by '#'

        Return a map, where each key is a tag and each value is a set of filenames
        corresponding to files which have the key tag.

        If only_existing is set to True, then only return existing files.

        """
        m = {}
        for t in self.tags:
            m[t] = set()
        for f in self.file_records:
            if only_existing and not f.file_exists:
                continue
            for t in f.tags:
                m[t].add(f.path)
        return m

    def get_matching_tagged_files(self, tags, only_existing=False):
        """
        Return a set of files which match all the given tags
        """
        if tags is None or len(tags) == 0:
            return []
        tagged_files_map = self.build_tagged_files_map(only_existing)

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

    def get_tags_from_files(self, files):
        """
        Return a list of tags which match the given files
        """
        tags = set()
        for f in self.file_records:
            if f.path in files:
                for tag in f.tags:
                    tags.add(tag)
        return list(tags)

    def find_record_for_path(self, pathname):
        for f in self.file_records:
            if f.path == pathname:
                return f
        return None

    def get_missing_files(self):
        """
        Return a list of files which are in the index but can't be found on the filesystem.
        """
        out = []
        for f in self.file_records:
            if not f.file_exists:
                out.append(f.path)
            pass
        return out

    def prune(self):
        """
        Remove files which are in the index but can't be found on the filesystem.
        """
        new_files = []
        not_found = 0
        for f in self.file_records:
            if f.file_exists:
                new_files.append(f)
            else:
                not_found += 1
        self.file_records = new_files
        if not_found > 0:
            print(f"{not_found} files pruned. Export and/or save recommended.")
        pass

    def write_file_records_to_file(self, filename):
        """
        Write the base data structure out to a text file.
        """
        self.file_records.sort(key=lambda r: r.path)
        file = open(filename, "w", encoding="utf-8")

        for f in self.file_records:
            print(f.path, file=file)
            for c in f.comments:
                print(c, file=file)
            tags = f.tags
            tags_list = list(tags)
            tags_list.sort()

            p = Util.paragraph_wrap(' '.join(tags_list), 72)

            print(p, file=file)
            print('', file=file)

        file.close()

    def find_duplicated_filenames(self):
        """
        Returns a list of filenames which are found in
        more than one pathname in the base data.
        TODO: Rewrite this whole function.
        """
        out = []
        base_names = set()
        for f in self.file_records:
            b = basename(f.path)
            if b in base_names:
                out.append(f.path)
            else:
                base_names.add(b)
        return out

    def export(self):
        """
        Write data out to a .txt file
        :return: the filename of the exported file.
        """

        now_file = Util.make_time_stamped_file_name('tags', 'txt')

        self.write_file_records_to_file(now_file)
        print(f'Results written to {now_file}')
        return now_file

    def make_m3u_for_text_match(self, term):
        """
        Writes out a m3u which matches a term (case-insensitive)
        """
        files = self.find_matching_files_for_text_term(term)
        paths = [f.path for f in files]
        paths.sort()
        if len(paths) > 0:
            filename = Util.write_m3u_file(paths, 'playlist')
            print(f'Wrote {len(paths)} files to {filename}')
        else:
            print('No records found.')
        pass

    def make_m3u_for_tags(self, tags):
        """
        Make a m3u playlist of all the files which contain all the passed
        tags.
        """
        filelist = list(self.get_matching_tagged_files(tags, only_existing=True))
        filelist.sort()
        if len(filelist) > 0:
            filename = Util.write_m3u_file(filelist, 'playlist')
            print(f'Wrote {len(filelist)} files to {filename}')
        else:
            print('No records found.')

    def find_matching_files_for_text_term(self, term):
        """
        Return a list of file structs which match term (case-insensitive)
        """
        out = []
        t = term.lower()
        for file in self.file_records:
            p = file.path.lower()
            if t in p:
                out.append(file)
            pass
        return out

    def find_matching_tags_for_text_term(self, term):
        """
        Return a list of tags which match term (case-insensitive)
        """
        out = []
        t = term.lower()
        for tag in self.tags:
            tag = tag.lower()
            if t in tag:
                out.append(tag)
            pass
        return out

    def find_untracked(self, data_directory=None, extensions=None):
        """
        Find files which aren't accounted for yet.
        """
        if extensions is None:
            extensions = Util.audio_extensions
        if data_directory is None:
            data_directory = main_data_directory
        untracked_files_list = []
        known_files = set()

        found_extensions = set()

        for f in self.file_records:
            known_files.add(f.path)

        gen = os.walk(data_directory)
        for rec in gen:
            dir_path = rec[0]
            # dir_names = rec[1]
            filenames = rec[2]
            for filename in filenames:
                path_tuple = os.path.splitext(filename)
                if len(path_tuple[1]) > 0:
                    ext = path_tuple[1][1:]
                    if ext not in extensions:
                        found_extensions.add(ext)
                        pass
                    pass

                if not Util.ends_with(filename, extensions):
                    continue

                path = os.path.join(dir_path, filename)
                if path not in known_files:
                    untracked_files_list.append(path)
                    pass
                pass
            pass
        filename = Util.make_time_stamped_file_name('untracked', 'm3u')
        f = open(filename, "w", encoding="utf-8")
        # TODO Break this out from this function.
        print('\n\n'.join(iter(untracked_files_list)), file=f)
        f.close()
        print(f'Wrote {len(untracked_files_list)} untracked files to {filename}')
        print(f'Other extensions = {found_extensions}')

    def move_if_tagged(self, ttag, ddir):
        """
        Find any files marked with the tag specified in ttag, and move them to a special
        directory as specified in ddir under the current working directory.
        """
        to_move = []
        n_moved = 0
        dest_folder = str(os.path.join(main_data_directory, ddir))
        if not os.path.exists(dest_folder):
            os.mkdir(dest_folder)
            pass
        for f in self.file_records:
            if ttag in f.tags:
                file_dir = os.path.dirname(f.path).split('\\')[-1]
                if file_dir != ddir:
                    to_move.append(f)
                    pass
                pass
            pass
        for f in to_move:
            file_name = os.path.split(f.path)[1]
            src = f.path
            dst = os.path.join(dest_folder, file_name)

            if os.path.exists(dst):
                print(f'I wanted to move `{src}` to `{dst}`, but `{dst}` already exists!')
            else:
                shutil.move(src, dst)
                print(f'Moved `{src}` to `{dst}`')
                n_moved += 1
                f.path = dst
                pass
            pass
        print(f'Moved {n_moved} files to {ddir}, out of {len(to_move)} requested.')
        if n_moved > 0:
            print('export() and/or save() recommended.')
            pass
        pass

    def delete(self):
        """
        Find any files marked with the tag 'to-delete' and move them to a special
        directory called '.trash'.
        """
        self.move_if_tagged('to-delete', '.trash')

    def favorite(self):
        """
        Find any files marked with the tag 'move-to-favorites' and move them to a special
        directory called '.favorites'.
        """
        self.move_if_tagged('move-to-favorites', '.favorites')

    def archive(self):
        """
        Find any files marked with the tag 'to-archive' and move them to a special
        directory called '.archive'.
        """
        self.move_if_tagged('to-archive', '.archive')

    def extract_all_tags(self):
        for f in self.file_records:
            if f.file_exists:
                new_tags = Util.extract_tags(f.path)
                f.tags.update(new_tags)
        pass

    def clean_all_tags(self):
        for f in self.file_records:
            old_tags = f.tags
            new_tags = set()
            for t in old_tags:
                new_tags.add(Util.transform_to_tag(t))
                pass
            f.tags = new_tags
            pass
        pass

    def replace_tag(self, target, replace):
        for f in self.file_records:
            if target in f.tags:
                f.tags.remove(target)
                f.tags.add(replace)
                pass
            pass
        if target in self.tags:
            self.tags.remove(target)
            self.tags.add(replace)
            pass
        pass

    def count_tags(self):
        tag_counts = {}
        for f in self.file_records:
            for t in f.tags:
                if t not in tag_counts:
                    tag_counts[t] = 0
                    pass
                tag_counts[t] += 1
                pass
            pass
        out = sorted(tag_counts.items(), key=lambda i: i[1], reverse=True)
        return out


# ######################################################################
# Utility
# ######################################################################
class Util:
    def __init__(self):
        pass

    video_extensions = [
        'wmv', 'mp4', 'mkv', 'mov', 'mpg', 'avi', 'm4v', 'MPG', 'MP4', 'MOV', 'mpeg'
    ]

    audio_extensions = [
        'ogg', 'wav', 'mp3'
    ]

    @staticmethod
    def paragraph_wrap(text_to_reflow, num_columns):
        """
        Restrict a string to <num_columns> width. Add newlines as necessary.
        Compresses multiple spaces between words into single spaces.
        TODO: Add test methods for this function.
        """
        sub_strings = list(filter(lambda c: len(c) > 0, text_to_reflow.split(' ')))
        out_list = []
        build = ''
        for i in range(0, len(sub_strings)):
            if len(sub_strings[i]) == 0:
                continue
            if len(build) + len(sub_strings[i]) < num_columns:
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
        return '\n'.join(out_list)

    @staticmethod
    def ends_with(filename, extensions=None):
        """
        Returns true if filename ends with one of the given extensions.
        :param filename:
        :param extensions:
        :return: True if the filename ends with an extension in <extensions>
        """
        if extensions is None:
            extensions = []
        for ext in extensions:
            if filename.endswith(ext):
                return True
            pass
        return False

    @staticmethod
    def make_time_stamped_file_name(prefix, suffix):
        """
        Make a filename which contains the time and date of creation
        :param prefix: a prefix to prepend to the new filename.
        :param suffix: a suffix to append to the new filename.
        :return: a filename in the form <prefix>-<date>-<time>.<suffix>
                 <date> will be in ISO-8601 format e.g. "2023-01-01".
                 <time> will be in the form <hour>-<minute>-<second>.
        """
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

    @staticmethod
    def write_m3u_file(path_list, prefix):
        m3u_filename = Util.make_time_stamped_file_name(prefix, 'm3u')
        f = open(m3u_filename, "w", encoding="utf-8")
        print('\n'.join(path_list), file=f)
        f.close()
        return m3u_filename
        pass

    @staticmethod
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

    @staticmethod
    def extract_tags(pathname):
        out = set()
        try:
            tag = TinyTag.get(pathname)
        except tinytag.tinytag.TinyTagException as e:
            print(f'WARNING: exception for {pathname}:')
            print(e)
            return out

        if tag.artist is not None and len(tag.artist) > 0:
            out.add('artist=' + Util.transform_to_tag(tag.artist))
        if tag.year is not None and len(tag.year) > 0:
            out.add('year=' + Util.transform_to_tag(tag.year))
        if tag.album is not None and len(tag.album) > 0:
            out.add('album=' + Util.transform_to_tag(tag.album))
        if tag.title is not None and len(tag.title) > 0:
            out.add('title=' + Util.transform_to_tag(tag.title))
        return out


# ######################################################################
# MainWindow
# ######################################################################
class MainWindow:
    # TODO: Put the data directory in the TagsForFilesObj and remove it from this ctor.
    def __init__(self, tags_for_files_obj: TagsForFiles, data_directory):
        self.tags_for_files_obj = tags_for_files_obj
        files_list = [record.path for record in tags_for_files_obj.file_records]
        tag_list = list(tags_for_files_obj.tags)
        tag_list.sort()
        self.layout = [
            [sg.Text(f'Base directory: {data_directory} | {len(files_list)} files | {len(tag_list)} tags')],
            [sg.HorizontalSeparator()],

            [sg.Column([[sg.Text('ALL FILES:'),
                         sg.DropDown(values=['Alpha', 'Selected'],
                                     default_value='Alpha',
                                     enable_events=True,
                                     readonly=True,
                                     size=30, key='FILES-DROPDOWN-SORT')],
                        [sg.Listbox(values=files_list,
                                    size=(100, 20),
                                    key='FILES-LISTBOX',
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
                                    key='TAGS-LISTBOX',
                                    select_mode=sg.LISTBOX_SELECT_MODE_EXTENDED,
                                    enable_events=True,
                                    horizontal_scroll=True)]])],

            [
                sg.Button('Edit selected files', key='EDIT_SELECTED_FILES_BUTTON', disabled=True),
                sg.Text(size=(80, 1), key='SELECTION_STATUS_TEXT')
            ],
            [sg.InputText('', size=(80, 1), key='FIND-ENTRY', enable_events=True),
             sg.Button('Find', key='FIND-BUTTON')],
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
                sg.InputText(size=(90, 1), key='FILE_OP_STATUS', use_readonly_for_disable=True, disabled=True),
            ],
            [sg.HorizontalSeparator()],
            [sg.Button('Quit')]
        ]
        self.window = sg.Window('Tags For Files', self.layout)

    def run(self):
        while True:
            event, values = self.window.read()
            print(event, values)
            # See if user wants to quit or window was closed
            if event == sg.WINDOW_CLOSED or event == 'Quit':
                break
            elif event == 'FILES-LISTBOX' or event == 'TAGS-LISTBOX':
                self.update_selection_display()
            elif event == '-CLEAR-FILES-':
                self.window['FILES-LISTBOX'].set_value([])
                self.update_selection_display()
            elif event == '-CLEAR-TAGS-':
                self.window['TAGS-LISTBOX'].set_value([])
                self.update_selection_display()
            elif event == 'SELECT-FILES-FROM-TAGS':
                self.select_files_from_tags()
                self.update_selection_display()
            elif event == 'SELECT-TAGS-FROM-FILES':
                self.select_tags_from_files()
                self.update_selection_display()
            elif event == 'TAGS-DROPDOWN-SORT':
                self.update_tags_sort_order()
            elif event == 'FILES-DROPDOWN-SORT':
                self.update_files_sort_order()
            elif event == 'EXPORT-BUTTON':
                self.do_export()
            elif event == 'PLAYLIST-BUTTON':
                self.do_make_playlist()
            elif event == 'FIND-BUTTON':
                self.do_find()
            elif event == 'EDIT_SELECTED_FILES_BUTTON':
                self.do_edit_selected_files()

            # Finish up by removing from the screen
        self.window.close()
        pass

    def select_files_from_tags(self):
        tags_list = self.window['TAGS-LISTBOX'].get()
        file_list = list(self.tags_for_files_obj.get_matching_tagged_files(tags_list))
        if file_list is None:
            file_list = []
        if self.window['REPLACE-OR-EXPAND-SELECTION'].get() == 'Expand':
            for f in self.window['FILES-LISTBOX'].get():
                if f not in file_list:
                    file_list.append(f)
        self.window['FILES-LISTBOX'].set_value(file_list)

    def update_selection_display(self):
        n_selected_files = len(self.window['FILES-LISTBOX'].get())
        n_selected_tags = len(self.window['TAGS-LISTBOX'].get())
        self.window['SELECTION_STATUS_TEXT'].update(f'Selected: {n_selected_files} files | {n_selected_tags} tags')
        self.window['EDIT_SELECTED_FILES_BUTTON'].update(disabled=(n_selected_files == 0))

    def select_tags_from_files(self):
        selected_files_list = self.window['FILES-LISTBOX'].get()
        tags_list = list(self.tags_for_files_obj.get_tags_from_files(selected_files_list))
        if tags_list is None:
            tags_list = []
        if self.window['REPLACE-OR-EXPAND-SELECTION'].get() == 'Expand':
            for t in self.window['TAGS-LISTBOX'].get():
                if t not in tags_list:
                    tags_list.append(t)
        self.window['TAGS-LISTBOX'].set_value(tags_list)

    def update_tags_sort_order(self):
        sort_order = self.window['TAGS-DROPDOWN-SORT'].get()
        selected = self.window['TAGS-LISTBOX'].get()
        tags_list = []

        if sort_order == 'Alpha':
            tags_list = list(self.tags_for_files_obj.tags)
            tags_list.sort()
        elif sort_order == 'Selected':
            tags_list = list(self.tags_for_files_obj.tags)
            augmented_tag_list = [(t, t in selected) for t in tags_list]
            sorted_tag_list = sorted(augmented_tag_list, key=lambda x: f' {x[0]}' if x[1] else x[0])
            tags_list = [t[0] for t in sorted_tag_list]
        elif sort_order == 'Frequency':
            tags_list = [item[0] for item in self.tags_for_files_obj.count_tags()]
        self.window['TAGS-LISTBOX'].update(tags_list)
        self.window['TAGS-LISTBOX'].set_value(selected)
        self.update_selection_display()

    def update_files_sort_order(self):
        sort_order = self.window['FILES-DROPDOWN-SORT'].get()
        selected = self.window['FILES-LISTBOX'].get()
        file_list = []
        if sort_order == 'Alpha':
            file_list = [f.path for f in self.tags_for_files_obj.file_records]
            file_list.sort()
        elif sort_order == 'Selected':
            file_list = [f.path for f in self.tags_for_files_obj.file_records]
            augmented_file_list = [(f, f in selected) for f in file_list]
            sorted_file_list = sorted(augmented_file_list, key=lambda x: f' {x[0]}' if x[1] else x[0])
            file_list = [f[0] for f in sorted_file_list]
        self.window['FILES-LISTBOX'].update(file_list)
        self.window['FILES-LISTBOX'].set_value(selected)
        self.update_selection_display()

    def do_export(self):
        self.window['FILE_OP_STATUS'].update('Writing export file')
        file_name = self.tags_for_files_obj.export()
        self.window['FILE_OP_STATUS'].update(f'Wrote {file_name}')

    def do_make_playlist(self):
        self.window['FILE_OP_STATUS'].update('Writing m3u file')
        files_list = self.window['FILES-LISTBOX'].get()
        filename = Util.make_time_stamped_file_name('playlist', 'm3u')
        f = open(filename, 'w', encoding='utf-8')
        print('\n'.join(files_list), file=f)
        f.close()
        status_message = f'Wrote {len(files_list)} files to {filename}'
        print(status_message)
        self.window['FILE_OP_STATUS'].update(status_message)

    def do_find(self):
        find_text = self.window['FIND-ENTRY'].get()
        if len(find_text) == 0:
            self.window['TAGS-LISTBOX'].set_value([])
            self.window['FILES-LISTBOX'].set_value([])
        else:
            file_matches = self.tags_for_files_obj.find_matching_files_for_text_term(find_text)
            self.window['FILES-LISTBOX'].set_value([f.path for f in file_matches])
            tag_matches = self.tags_for_files_obj.find_matching_tags_for_text_term(find_text)
            self.window['TAGS-LISTBOX'].set_value(tag_matches)
        self.update_selection_display()

    def do_edit_selected_files(self):
        paths_list = self.window['FILES-LISTBOX'].get()
        # Gather the corresponding file records
        file_records_list = [self.tags_for_files_obj.find_record_for_path(p) for p in paths_list]
        edit_files_window = EditFilesWindow(file_records_list)
        edit_files_window.run()


# ######################################################################
# EditFilesWindow
# ######################################################################
class EditFilesWindow:
    def __init__(self, list_of_file_records):
        self.file_records = list_of_file_records
        self.cursor = 0
        self.layout = [
            [sg.InputText(list_of_file_records[0].path,
                          size=(120, 1), key='EDIT_FILE_RECORD_PATH',
                          use_readonly_for_disable=True, disabled=True)],
            [sg.Listbox(list_of_file_records[0].tags,
                        size=(120, 10), key='EDIT_FILE_RECORD_TAGS',
                        enable_events=True)],
            [sg.InputText('', size=(90, 1), key='EDIT_FILE_RECORD_TAG_EDIT',
                          enable_events=True, focus=True, expand_x=True),
             sg.Button('Add', key='EDIT_FILE_RECORD_ADD_TAG',
                       bind_return_key=True)],
            [sg.HorizontalSeparator()],
            [
                sg.Button('Prev Record', key='EDIT_FILE_PREV_RECORD_BUTTON', disabled=True,
                          expand_x=True),
                sg.Button('Next Record', key='EDIT_FILE_NEXT_RECORD_BUTTON',
                          disabled=len(list_of_file_records) < 2,
                          expand_x=True),
            ],
            [sg.HorizontalSeparator()],
            [sg.Button('Back')]
        ]
        edit_window_title = f'Editing {len(list_of_file_records)} File Records'
        self.window = sg.Window(edit_window_title, self.layout,
                                modal=True, finalize=True,
                                # return_keyboard_events=True
                                )
        self.window['EDIT_FILE_RECORD_TAG_EDIT'].set_focus(True)

    def increment_cursor_position(self, increment):
        new_value = self.cursor + increment
        if 0 <= new_value < len(self.file_records):
            self.cursor = new_value
        self.window['EDIT_FILE_PREV_RECORD_BUTTON'].update(disabled=(self.cursor == 0))
        self.window['EDIT_FILE_NEXT_RECORD_BUTTON'].update(
            disabled=(self.cursor == (len(self.file_records) - 1)))
        self.window['EDIT_FILE_RECORD_PATH'].update(value=self.file_records[self.cursor].path)
        self.window['EDIT_FILE_RECORD_TAGS'].update(values=self.file_records[self.cursor].tags)
        self.window['EDIT_FILE_RECORD_TAG_EDIT'].set_focus(True)
        self.window['EDIT_FILE_RECORD_TAG_EDIT'].update(value='')

    def run(self):
        while True:
            event, values = self.window.read()
            # print(event, values)
            if event == sg.WINDOW_CLOSED or event == 'Back':
                break
            elif event == 'EDIT_FILE_PREV_RECORD_BUTTON':
                self.increment_cursor_position(-1)
            elif event == 'EDIT_FILE_NEXT_RECORD_BUTTON':
                self.increment_cursor_position(1)
            elif event == 'EDIT_FILE_RECORD_TAG_EDIT':
                s = self.window['EDIT_FILE_RECORD_TAG_EDIT'].get()
                print(s)
                if len(s.strip()) > 0:
                    c = s[-1]
                    if c == ' ':
                        new_tag = s.strip()
                        if len(new_tag) > 0:
                            print(f'Accepting new tag <{new_tag}>')
                            self.window['EDIT_FILE_RECORD_TAG_EDIT'].update(value='')
                    if c == '\t':
                        print('TAB')
                    if c == '\n':
                        print('RETURN')

        self.window.close()


# ######################################################################
# Main Loop
# ######################################################################
if __name__ == '__main__':
    # ######################################################################
    # Parse arguments and set up primary data structures
    # ######################################################################
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

    text_file_path = os.path.join(main_data_directory, "tags.txt")
    text_file_path = os.path.abspath(text_file_path)
    print(f'text_file_path = {text_file_path}')

    mainTagsForFilesObj = TagsForFiles()

    # Data format is as follows:
    # A record consists of a sequence of non-blank lines.
    # - The first line contains the file path
    # - An optional number of lines after the path contains file comments,
    #   indicated by the presence of a '#' as the first character of the line.
    # - Every subsequent non-blank line contains tags, each separated by 1 or more spaces.
    # - A tag in the form '<k>=<v>' where k and v are both valid strings is considered
    #   to be a variable, with the name k and the value v.
    # - Complete records are separated by one or more blank lines.
    mainTagsForFilesObj.import_text_data_from_file(text_file_path)
    pp = pprint.PrettyPrinter(indent=2)

    print()
    print(f"Read {len(mainTagsForFilesObj.file_records)} files.")

    print()
    print(f"Read {len(mainTagsForFilesObj.tags)} tags.")

    print()
    missing_files = mainTagsForFilesObj.get_missing_files()
    print(f'{len(missing_files)} Missing files.')

    print()
    possible_dupes = mainTagsForFilesObj.find_duplicated_filenames()
    print(f'{len(possible_dupes)} Possibly-duplicated files.')

    print()

    mainTagsForFilesObj.export()

    mainTagsForFilesObj.find_untracked(main_data_directory, Util.video_extensions)

    print('Use `mainTagsForFilesObj.export()` to write to a text file tags list')
    print('Use `mainTagsForFilesObj.find_matching(term) to find file names which match a search term')
    print('Use `mainTagsForFilesObj.get_matching_tagged_files(tags)` to get a list of files which match tags')
    print('Use `mainTagsForFilesObj.make_m3u_for_tags(tags)` to make a playlist of the given tags')
    print('Use `mainTagsForFilesObj.make_m3u_for_text_match(term)` to make a playlist matching the given term')
    print('Use `mainTagsForFilesObj.find_untracked(extensions)` to make a list of untracked files.')
    print('Use `mainTagsForFilesObj.get_missing_files()` to find files which are indexed but not on the filesystem.')
    print('Use `mainTagsForFilesObj.extract_all_tags()` to pull tags out of embedded metadata.')
    print('Use `mainTagsForFilesObj.delete()` to move files marked with the `to-delete` tag to `.trash`')
    print('Use `mainTagsForFilesObj.favorite()` to move files marked with the `move-to-favorites` tag to `.favorites`')
    print('Use `mainTagsForFilesObj.archive()` to move files marked with the `to-archive` tag to `.archive`')

    MainWindow(mainTagsForFilesObj, main_data_directory).run()

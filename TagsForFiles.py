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

import tinytag
from tinytag import TinyTag

# TODO: Investigate mp3tag (https://mp3tag.de/en)

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
        self.edited = False

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
    def __init__(self, tags_file_path=None):
        self.tags_file_path = tags_file_path
        self.tags = set()
        self.file_records = []
        self.edited = False

        if tags_file_path is not None:
            self.import_text_data_from_file(self.tags_file_path)

    def get_base_directory(self):
        if self.tags_file_path is not None:
            return os.path.dirname(self.tags_file_path)

    def add_file_record(self, file_record):
        file_record.id = len(self.file_records)
        file_record.edited = False
        self.edited = True
        self.file_records.append(file_record)
        self.tags.update(file_record.tags)

    def add_path(self, path):
        """
        Add a file record for the given path.
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
        self.tags_file_path = filename
        file = open(filename, encoding='utf-8')
        data = file.readlines()
        file.close()
        self.import_text_data(data)

    def get_untagged_files(self, only_existing=False):
        m = []
        for f in self.file_records:
            if only_existing and not f.file_exists:
                continue
            elif len(f.tags) == 0:
                m.append(f.path)
        return m

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

    def make_m3u_for_untagged_files(self):
        paths = self.get_untagged_files()
        paths.sort()
        if len(paths) > 0:
            filename = Util.write_m3u_file(paths, 'playlist')
            print(f'Wrote {len(paths)} files to {filename}')
        else:
            print('No records found.')
        pass


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

    def find_untracked(self, data_directory=None, extensions=None, write_m3u_file=True):
        """
        Find files which aren't accounted for yet.
        """
        if extensions is None:
            extensions = Util.media_extensions
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

        if write_m3u_file:
            if len(untracked_files_list) > 0:
                # TODO: Break this out from this function.
                filename = Util.make_time_stamped_file_name('untracked', 'm3u')
                f = open(filename, "w", encoding="utf-8")
                print('\n\n'.join(iter(untracked_files_list)), file=f)
                f.close()
                print(f'Wrote {len(untracked_files_list)} untracked files to {filename}')
                print(f'Other extensions = {found_extensions}')
            else:
                print('No untracked files were found.')
        return untracked_files_list

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
        n_records = len(self.file_records)
        index = 0
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
            f.edited = True
            pass
        pass
        self.edited = True

    def replace_tag(self, target, replace):
        for f in self.file_records:
            if target in f.tags:
                f.tags.remove(target)
                f.tags.add(replace)
                f.edited = True
                pass
            pass
        if target in self.tags:
            self.tags.remove(target)
            self.tags.add(replace)
            self.edited = True
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

    media_extensions = video_extensions + audio_extensions

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
        to_remove = '/,()\'\"!&%;^$#@<>{}[]\\|?*~` \r\t\n'  # These characters have no business in a tag

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

    mainobj = TagsForFiles(text_file_path)
    print(f'tags file base = {mainobj.get_base_directory()}')

    # Data format is as follows:
    # A record consists of a sequence of non-blank lines.
    # - The first line contains the file path
    # - An optional number of lines after the path contains file comments,
    #   indicated by the presence of a '#' as the first character of the line.
    # - Every subsequent non-blank line contains tags, each separated by 1 or more spaces.
    # - A tag in the form '<k>=<v>' where k and v are both valid strings is considered
    #   to be a variable, with the name k and the value v.
    # - Complete records are separated by one or more blank lines.
    pp = pprint.PrettyPrinter(indent=2)

    print()
    print(f"Read {len(mainobj.file_records)} files.")

    print()
    print(f"Read {len(mainobj.tags)} tags.")

    print()
    missing_files = mainobj.get_missing_files()
    print(f'{len(missing_files)} Missing files.')

    print()
    possible_dupes = mainobj.find_duplicated_filenames()
    print(f'{len(possible_dupes)} Possibly-duplicated files.')

    print()

    mainobj.export()

    mainobj.find_untracked(main_data_directory, Util.media_extensions)

    
    print(f"{mainobj=}")
    

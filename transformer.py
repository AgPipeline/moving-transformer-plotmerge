"""Performs plot-level clipping on geo referenced files
"""

import argparse
import copy
import datetime
import logging
import os
import shutil
import subprocess

import terrautils.lemnatec

import configuration
import transformer_class

terrautils.lemnatec.SENSOR_METADATA_CACHE = os.path.dirname(os.path.realpath(__file__))

# A list of file name extensions that are supported
ACCEPTABLE_FILE_EXTENSIONS = ['.las']

class __internal__():
    """Class for internal use only functions
    """

    def __init__(self):
        """Initializes class instance
        """

    @staticmethod
    def get_files_to_process(source_names: list, acceptable_extensions: list) -> list:
        """Returns the list of files to process by checking into folders
        Arguments:
            source_names: the list of names to investigate
            acceptable_extensions: a list of acceptable file extensions
        Return:
            Returns a list of files to process
        """
        return_names = []
        for one_name in source_names:
            if not os.path.exists(one_name):
                logging.info("Ignoring missing file: '%s'", one_name)
                continue

            if os.path.isdir(one_name):
                return_names.extend(__internal__.get_files_to_process(os.listdir(one_name), acceptable_extensions))
            else:
                for one_extension in acceptable_extensions:
                    if one_name.endswith(one_extension):
                        return_names.append(one_name)

        return return_names

    @staticmethod
    def merge_las(las_path: str, merged_path: str) -> None:
        """Merges LAS files
        Arguments:
          las_path: path to point cloud file to merge
          merged_path: optional path to write merged data to
        Exceptions:
            Raises RuntimeError if the merged_path is invalid
        """
        # Merge if we already have a destination file, otherwise just copy
        if os.path.isfile(merged_path):
            cmd = 'pdal merge "%s" "%s" "%s"' % (las_path, merged_path, merged_path)
            logging.debug("Running merge command: '%s'", cmd)
            subprocess.call([cmd], shell=True)
        else:
            logging.debug("Nothing to merge: copying '%s' to '%s'", las_path, merged_path)
            shutil.copy(las_path, merged_path)

    @staticmethod
    def check_already_merged(merged_file: str, source_file: str) -> bool:
        """Checks if the source file is listed in the merged file
        Arguments:
            merged_file: path to the merged file to check
            source_file: the name of the source file to look for
        Return:
            Returns True if the source file name is found in the contents of the merged file and False otherwise
        """
        already_merged = False
        if os.path.exists(merged_file):
            # Check if contents
            with open(merged_file, 'r') as contents:
                for entry in contents.readlines():
                    if entry.strip() == source_file:
                        already_merged = True
                        break
        return already_merged

    @staticmethod
    def prepare_file_md(filepath: str, source_file: str, key_value: str) -> dict:
        """Prepares the metadata for a single file
        Arguments:
            filepath: the path of the file to prepare metadata for
            source_file: the source file that was merged in
            key_value: the key value associated with this file
        Return:
            The formatted metadata
        """
        cur_md = {
            'path': filepath,
            'key': key_value,
            'metadata': {
                'replace': True,
                'data': {
                    'source': [source_file],
                    'transformer': configuration.TRANSFORMER_NAME,
                    'version': configuration.TRANSFORMER_VERSION,
                    'timestamp': datetime.datetime.utcnow().isoformat()
                }
            }
        }

        return cur_md

    @staticmethod
    def merge_file_dict(source_md: dict, merge_md: dict, recursion_depth: int = 0) -> dict:
        """Merges dictionaries of file metadata
        Arguments:
            source_md: the source file metadata
            merge_md: the metadata to merge in
            recursion_depth: the number of levels to recurse when copying dict (<=1 is no recursion)
        Return:
            Returns the combined metadata.
        Note:
            A deep copy of the source metadata is made and updated before it's returned.
            Types that are not mutable, such as strings and lists, are copied and not combined.
            Types of 'list' are merged through list.extend().
            Types of 'dict' are merged in depth, up to recursion_depth, with types merged as described (eg: 'list', et. al.).
            Dictionaries encountered at the end of recursion depth are shallow merged with merge_md values taking
            precedence over existing values; for example: dest_md[key] = {**src_md[key], **merge_md[key]}.
        """
        if not source_md:
            return merge_md if merge_md else {}

        return_md = copy.deepcopy(source_md)

        # Setup key arrays to loop through
        return_key_set = set(return_md.keys())
        merge_keys = merge_md.keys()
        common_keys = [k for k in merge_keys if k in return_key_set]
        new_keys = [k for k in merge_keys if k not in return_key_set]

        # Only merge fields that are arrays, set, or dict, copy the rest
        for one_key in common_keys:
            one_value = return_md[one_key]
            new_value = merge_md[one_key]
            if isinstance(one_value, list):
                if isinstance(new_value, list):
                    return_md[one_key].extend(new_value)
                else:
                    logging.debug("Ignoring attempt to merge list metadata key '%s' with non-list type: %s", one_key,
                                  type(new_value))
            elif isinstance(one_value, dict):
                if isinstance(new_value, dict):
                    if recursion_depth > 1:
                        return_md[one_key] = __internal__.merge_file_dict(one_value, new_value, recursion_depth - 1)
                    else:
                        return_md[one_key] = {**one_value, **new_value}
                else:
                    logging.warning("Ignoring attempt to merge dict metadata key '%s' with non-dict type: %s", one_key,
                                    type(new_value))
            else:
                return_md[one_key] = merge_md[one_key]

        # Check for new keys in the metadata to merge
        for one_key in new_keys:
            return_md[one_key] = merge_md[one_key]

        return return_md

    @staticmethod
    def merge_file_md(dest_md: list, new_md: dict) -> list:
        """Merges file level metadata ensuring there aren't any duplicate file entries
        Arguments:
            dest_md: the list of current metadata to merge into
            new_md: the new metadata to merge
        Return:
            Returns a new list of metadata with the new metadata merged into it
        """
        # Return something meaningful if we have missing or empty dict
        if not dest_md:
            if new_md:
                return [new_md]
            return []

        # Look for a match
        match_idx = -1
        md_len = len(dest_md)
        for idx in range(0, md_len):
            if dest_md[idx]['path'] == new_md['path']:
                match_idx = idx
                break

        # If no match found, add new metadata and return
        if match_idx == -1:
            dest_md.append(new_md)
            return dest_md

        # If there isn't file-level metadata to merge, just return
        if 'metadata' not in new_md or 'data' not in new_md['metadata']:
            # The entry already exists in dest metadata and there's nothing to merge
            return dest_md

        # Merge the metadata
        working_md = dest_md[match_idx]
        if 'metadata' in working_md:
            if 'data' in working_md['metadata']:
                working_md['metadata']['data'] = __internal__.merge_file_dict(working_md['metadata']['data'], new_md['metadata']['data'])
        else:
            # We have checked that new_md has 'metadata' key earlier
            working_md['metadata'] = new_md['metadata']
        # Save new/modified metadata
        dest_md[match_idx] = working_md

        return dest_md


def add_parameters(parser: argparse.ArgumentParser) -> None:
    """Adds parameters
    Arguments:
        parser: instance of argparse
    """
    parser.add_argument('--merge_filename', type=str, default=None, help='override of the output file name')

    parser.add_argument('sensor', type=str, help='the name of the sensor associated with the source files')


def perform_process(transformer: transformer_class.Transformer, check_md: dict, transformer_md: dict, full_md: dict) -> dict:
    """Performs the processing of the data
    Arguments:
        transformer: instance of transformer class
        check_md: metadata associated with this request
        transformer_md: metadata associated with this transformer
        full_md: the full set of metadata
    Return:
        Returns a dictionary with the results of processing
    """
    # pylint: disable=unused-argument
    # loop through the available files and merge data into top-level files
    processed_files = 0
    las_processed_files = 0
    start_timestamp = datetime.datetime.now()
    file_list = __internal__.get_files_to_process(check_md['list_files'](), ACCEPTABLE_FILE_EXTENSIONS)
    logging.info("Have %s files to process", str(len(file_list)))

    file_md = []
    for filepath in file_list:
        processed_files += 1

        filename = os.path.basename(filepath)

        if filename.endswith('.las'):
            # If file is LAS, we can merge with any existing scan+plot output safely
            out_path = check_md['working_folder']
            if transformer.args.merge_filename:
                merged_out = os.path.join(out_path, os.path.splitext(os.path.basename(transformer.args.merge_filename))[0] + '_merged.las')
            else:
                merged_out = os.path.join(out_path, os.path.splitext(os.path.basename(filename))[0] + '_merged.las')
            merged_txt = merged_out.replace('.las', '_contents.txt')
            if not os.path.exists(out_path):
                os.makedirs(out_path)

            if not __internal__.check_already_merged(merged_txt, filepath):
                logging.debug("Merging '%s' into '%s'", filepath, merged_out)
                __internal__.merge_las(filepath, merged_out)
                with open(merged_txt, 'a') as contents:
                    contents.write(filename + "\n")

                cur_md = __internal__.prepare_file_md(merged_out, filepath, transformer.args.sensor)
                file_md = __internal__.merge_file_md(file_md, cur_md)

                las_processed_files += 1
            else:
                logging.info("Skipping already merged LAS data: '%s'", filepath)

    return {
        'code': 0,
        'file': file_md,
        configuration.TRANSFORMER_NAME:
        {
            'utc_timestamp': datetime.datetime.utcnow().isoformat(),
            'processing_time': str(datetime.datetime.now() - start_timestamp),
            'total_file_count': len(file_list),
            'processed_file_count': processed_files,
            'las_file_count': las_processed_files,
            'sensor': transformer.args.sensor
        }
    }

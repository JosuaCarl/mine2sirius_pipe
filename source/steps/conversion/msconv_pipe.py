#!/usr/bin/env python

"""
Conversion of manufacturer MS files to .mzML or .mzXMLtarget_format. The folder structure is mimiced at the place of the output.
"""

import os
import argparse
import regex

from os.path import join
from tqdm.auto import tqdm

from source.steps.general import *


def main(args: argparse.Namespace | dict, unknown_args: list[str] = []):
	"""
	Execute the conversion.

	:param args: Command line arguments
	:type args: argparse.Namespace|dict
	:param unknown_args: Command line arguments that are not known.
	:type unknown_args: list[str]
	"""
	# Extract arguments
	in_dir = get_value(args, "in_dir")
	out_dir = get_value(args, "out_dir")
	target_format = get_value(args, "target_format", "mzML")
	pattern = get_value(args, "pattern", r"")
	suffix = get_value(args, "suffix", None)
	prefix = get_value(args, "prefix", None)
	contains = get_value(args, "contains", None)
	redo_threshold = get_value(args, "redo_threshold", 1e8)
	overwrite = get_value(args, "overwrite", False)
	nested = get_value(args, "nested", False)
	n_workers = get_value(args, "workers", 1)
	save_log = get_value(args, "save_log", False)
	platform = get_value(args, "platform", "windows")
	verbosity = get_value(args, "verbosity", 1)
	additional_args = get_value(args, "msconv_arguments")
	additional_args = additional_args if additional_args else unknown_args

	# Conversion
	msconvert_runner = MSconvert_Runner(
		platform=platform,
		target_format=target_format,
		pattern=pattern,
		suffix=suffix,
		prefix=prefix,
		contains=contains,
		redo_threshold=redo_threshold,
		overwrite=overwrite,
		save_log=save_log,
		additional_args=additional_args,
		verbosity=verbosity,
		nested=nested,
		workers=n_workers,
		scheduled_in=in_dir,
		scheduled_out=out_dir,
	)
	return msconvert_runner.run()


class MSconvert_Runner(Pipe_Step):
	"""
	General class for file conversion along matched patterns.
	"""

	def __init__(
		self,
		exec_path: StrPath = "msconvert",
		platform: str = "windows",
		target_format: str = "mzML",
		pattern: str = r".*",
		suffix: str = None,
		prefix: str = None,
		contains: str = None,
		redo_threshold: float = 1e8,
		overwrite: bool = False,
		save_log=False,
		additional_args: list = [],
		verbosity=1,
		**kwargs,
	):
		"""
		Initializes the file converter.

		:param exec_path: Path of executive
		:type exec_path: StrPath
		:param platform: Operational system/platform of computation, defaults to "windows"
		:type platform: str, optional
		:param target_format: _description_, defaults to "mzML"
		:type target_format: str, optional
		:param pattern: Pattern for folder matching, defaults to ""
		:type pattern: str, optional
		:param suffix: Suffix for folder matching, defaults to None
		:type suffix: str, optional
		:param prefix: Prefix for folder matching, defaults to None
		:type prefix: str, optional
		:param contains: Contained strings for folder matching, defaults to None
		:type contains: str, optional
		:param redo_threshold: Threshold in bytess for a target file to be considered as incomplete and scheduled for re running the conversion, defaults to 1e8
		:type redo_threshold: float, optional
		:param overwrite: Overwrite all, do not check whether file already exists, defaults to False
		:type overwrite: bool, optional
		:param save_log: Whether to save the output(s).
		:type save_log: bool, optional
		:param additional_args: Additional arguments for mzmine, defaults to []
		:type additional_args: list, optional
		:param verbosity: Level of verbosity, defaults to 1
		:type verbosity: int, optional
		"""
		super().__init__(
			exec_path=exec_path,
			platform=platform,
			patterns={"in": pattern},
			save_log=save_log,
			additional_args=additional_args,
			verbosity=verbosity,
		)
		if kwargs:
			self.update(kwargs)
		self.redo_threshold = redo_threshold
		self.overwrite = overwrite
		self.target_format = target_format if target_format.startswith(".") else f".{target_format}"
		self.target_format = change_case_str(
			s=self.target_format, range=slice(3, len(self.target_format)), conversion="upper"
		)
		self.pattern = pattern
		self.suffix = suffix
		self.prefix = prefix
		self.contains = contains
		self.name = "msconvert"

		self.update_regex(pattern=pattern, contains=contains, suffix=suffix, prefix=prefix)

	def update_regex(
		self, pattern: str = ".*", contains: str = None, suffix: str = None, prefix: str = None
	):
		pattern = pattern if pattern else self.pattern
		contains = contains if contains else self.contains
		suffix = suffix if suffix else self.suffix
		prefix = prefix if prefix else self.prefix
		if contains:
			pattern = rf"({pattern})|(.*{contains}.*)"
		if suffix:
			pattern = rf"{pattern}.*{suffix}$"
		if prefix:
			pattern = rf"^{prefix}.*{pattern}"
		self.patterns["in"] = pattern

	def select_for_conversion(self, in_path: str, out_path: str) -> bool:
		"""
		Convert one file with msconvert.

		:param in_path: Path to scheduled file.
		:type in_path: str
		:param out_path: Path to output directory.
		:type out_path: str
		:return: Whether the file was converted
		:rtype: bool
		"""
		# Check origin
		in_valid = super().match_file_name(pattern=self.patterns["in"], file_name=in_path)
		# Check target
		out_valid = (
			self.overwrite
			or (not os.path.isfile(out_path))
			or os.path.getsize(out_path) < float(self.redo_threshold)
			or not regex.search("^</.*>$", open_last_line_with_content(filepath=out_path))
		)

		return in_valid, out_valid

	def run_single(self, in_path: str, out_path: str):
		"""
		Convert one file with msconvert.

		:param in_path: Path to scheduled file.
		:type in_path: str
		:param out_path: Path to output directory.
		:type out_path: str
		"""
		out_file_name = ".".join(os.path.basename(in_path).split(".")[:-1]) + self.target_format

		cmd = (
			rf'"{self.exec_path}" --{self.target_format[1:]} -e {self.target_format} --64 '
			+ rf'-o "{out_path}" --outfile "{out_file_name}" "{in_path}" {" ".join(self.additional_args)}'
		)

		if not os.path.isfile(out_path):
			out_path = os.path.join(out_path, out_file_name)

		super().compute(cmd=cmd, in_path=in_path, out_path=out_path)

	def run_directory(self, in_path: str, out_path: str):
		"""
		Convert all matching files in a folder.

		:param in_path: Path to scheduled file.
		:type in_path: str
		:param out_path: Path to output directory.
		:type out_path: str
		"""
		verbose_tqdm = self.verbosity >= 2
		for entry in tqdm(os.listdir(in_path), disable=verbose_tqdm, desc="Converting folder"):
			entry_path = join(in_path, entry)
			hypothetical_out_path = join(out_path, replace_file_ending(entry, self.target_format))
			in_valid, out_valid = self.select_for_conversion(
				in_path=entry_path, out_path=hypothetical_out_path
			)

			if in_valid and out_valid:
				self.run_single(in_path=entry_path, out_path=out_path)

	def run_nested(self, in_root_dir: StrPath, out_root_dir: StrPath, recusion_level: int = 0):
		"""
		Converts multiple files in multiple folders, found in in_root_dir with msconvert and saves them
		to a location out_root_dir again into their respective folders.

		:param in_root_dir: Starting folder for descent.
		:type in_root_dir: StrPath
		:param out_root_dir: Folder where structure is mimiced and files are converted to
		:type out_root_dir: StrPath
		:param recusion_level: Current level of recursion, important for determination of level of verbose output, defaults to 0
		:type recusion_level: int, optional
		"""
		verbose_tqdm = self.verbosity >= recusion_level + 2
		made_out_root_dir = False

		for entry in tqdm(
			os.listdir(in_root_dir), disable=verbose_tqdm, desc="Schedule conversions"
		):
			entry_path = join(in_root_dir, entry)
			hypothetical_out_path = join(
				out_root_dir, replace_file_ending(entry, self.target_format)
			)
			in_valid, out_valid = self.select_for_conversion(
				in_path=entry_path, out_path=hypothetical_out_path
			)

			if in_valid and out_valid:
				if not made_out_root_dir:
					os.makedirs(out_root_dir, exist_ok=True)
					made_out_root_dir = True
				self.run_single(in_path=entry_path, out_path=out_root_dir)
			elif os.path.isdir(entry_path) and not in_valid:
				self.run_nested(
					in_root_dir=entry_path,
					out_root_dir=join(out_root_dir, entry),
					recusion_level=recusion_level + 1,
				)


if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		prog="msconv_pipe.py",
		description="Conversion of manufacturer MS files to .mzML or .mzXML target_format.\
                                             The folder structure is mimiced at the place of the output.",
	)
	parser.add_argument("-in", "--in_dir", required=True)
	parser.add_argument("-out", "--out_dir", required=True)
	parser.add_argument("-tf", "--target_format", required=False)
	parser.add_argument("-pat", "--pattern", required=False)
	parser.add_argument("-suf", "--suffix", required=False)
	parser.add_argument("-pre", "--prefix", required=False)
	parser.add_argument("-con", "--contains", required=False)
	parser.add_argument("-rt", "--redo_threshold", required=False)
	parser.add_argument("-o", "--overwrite", required=False, action="store_true")
	parser.add_argument("-n", "--nested", required=False, action="store_true")
	parser.add_argument("-w", "--workers", required=False, type=int)
	parser.add_argument("-s", "--save_log", required=False, action="store_true")
	parser.add_argument("-plat", "--platform", required=False)
	parser.add_argument("-v", "--verbosity", required=False, type=int)
	parser.add_argument("-msconv", "--msconv_arguments", required=False, nargs=argparse.REMAINDER)

	args, unknown_args = parser.parse_known_args()
	main(args=args, unknown_args=unknown_args)

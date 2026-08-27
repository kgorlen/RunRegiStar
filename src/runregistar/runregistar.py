import argparse
import glob
import os
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path
from typing import NoReturn

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
"""Path to directory containing this Python script."""
sys.path.append(str(SCRIPT_DIR))
"""Allow runstarnet CLI to import modules from script directory."""

# pylint: disable=wrong-import-position
from __init__ import __version__  # pylint: disable=no-name-in-module

# pylint: enable=wrong-import-position

# Global Constants

SCRIPT_NAME: str = os.path.basename(__file__).split(".")[0]
"""Name of this script without .py extension."""
REGISTAR_EXECUTABLE_PATHS = [
    r"C:\Program Files\Auriga Imaging\RegiStar\RegiStar.exe",
    r"C:\Program Files (x86)\Auriga Imaging\RegiStar\RegiStar.exe",
]
"""Possible paths to RegiStar executable."""

# Global Variables
ARGS: argparse.Namespace
"""Parsed command-line arguments."""


def cleanup_and_exit(status: int = 0) -> NoReturn:
    """Clean up and exit with the given status code."""
    print(f"{SCRIPT_NAME} finished.")
    input("Press Enter to exit ...")

    sys.exit(status)


def fatal_error(msg: str) -> NoReturn:
    """Print a CRITICAL message and sys.exit(1)."""
    print(f"CRITICAL - {msg}; exiting.", file=sys.stderr)
    cleanup_and_exit(1)


def prompt_yes_no(question: str, default: bool = True) -> bool:
    """Prompt for yes/no response.

    Args:
        question (str): Question to ask the user.
        default (bool, optional): Default value if the user doesn't provide an answer. Defaults to True.

    Returns:
        bool: User's response.
    """
    while True:
        response = input(f"{question} (y/n) [{('y' if default else 'n')}]: ").strip().lower()
        if response == "":
            return default
        elif response in ["y", "yes"]:
            return True
        elif response in ["n", "no"]:
            return False
        else:
            print("Please enter 'y' for yes or 'n' for no.")


def file_path_generator(
    globs: list[str], pattern: str | list[str] | None = "*", recursive: bool = True
) -> Generator[Path, None, None]:
    """Generate matched files from a list of files and/or directories with
    globbing, environment variable substitution, '~' expansion, and optional
    '**' recursion.

    Parameters
    ----------
    globs : list[str]
        List of file and directory paths to process.
    pattern : Optional[str], optional
        Glob pattern to match files, by default "*"
    recursive : bool, optional
        Process "**" directories recursively, by default True

    Yields
    ------
    Generator[Path, None, None]
        List of Path objects for matched files.

    Raises
    ------
    ValueError           If file name does not match allowed patterns.
    FileNotFoundError    File not found or not accessible.
    """
    assert pattern is not None

    # Convert pattern to list[str]
    patterns = [pattern] if isinstance(pattern, str) else pattern

    def expand_glob(glob_pattern: str) -> Generator[Path, None, None]:
        """Expand a glob

        Parameters
        ----------
        glob_pattern : str
            A glob.

        Yields
        ------
        Generator[Path, None, None]
            File paths from expanded glob.

        Raises
        ------
        ValueError           If file name does not match allowed patterns.
        FileNotFoundError    File not found or not accessible.
        """

        for filename in (
            glob.iglob(glob_pattern, recursive=recursive)
            if glob.has_magic(glob_pattern)
            else [glob_pattern]
        ):
            path = Path(os.path.expanduser(os.path.expandvars(filename)))
            if not any(path.match(p) for p in patterns):
                raise ValueError(f'Invalid file name "{filename}"')
            if not path.is_file():
                raise FileNotFoundError(f'File not found or not accessible: "{filename}"')
            yield path

    for glob_pattern in globs:
        path = Path(os.path.expanduser(os.path.expandvars(glob_pattern)))
        if path.is_dir():
            for p in patterns:
                yield from expand_glob(str(path / p))
        else:
            yield from expand_glob(glob_pattern)


def prompt_int(question: str, min: int, max: int, default: int | None = None) -> int:
    """Prompt for integer response.

    Args:
        question (str): Question to ask the user.
        min (int): Minimum allowed value.
        max (int): Maximum allowed value.
        default (int | None, optional): Default value if the user doesn't provide an answer. Defaults to None.

    Returns:
        int: User's response.
    """
    while True:
        response = input(
            f"{question} ({min} to {max}){('' if default is None else f' [{default}]')}: "
        ).strip()
        if response == "" and default is not None:
            return default
        try:
            value = int(response)
            if min <= value <= max:
                return value
            raise ValueError
        except ValueError:
            print(f"Please enter a number between {min} and {max}.")


def register(
    image_paths: list[Path], script: list[str], stack_num: int = 0, base_index: int = 0
) -> tuple[list[str], list[str]]:

    open_images: list[str] = []
    """List of open image IDs SnnIii, nn = stack number, ii = image number in stack."""
    reg_images: list[str] = []
    """List of registered image IDs, R_SnnIii."""

    for file_index, file_path in enumerate(image_paths, 1):
        image: str = f"S{stack_num:02d}I{file_index:02d}"
        script.append(f'{image} = Open( "{file_path.name}" )')
        script.append(f"Describe({image})")
        open_images.append(image)

    first_index = 1 if base_index == 0 else 0
    reg_images.append(f"R_{open_images[first_index]}")
    """Registration result ID."""
    script.append(f"{reg_images[-1]} = Register[0,0,0,0,1]( {open_images[first_index]}, {open_images[base_index]} )")
    script.append(f"Describe({reg_images[-1]})")

    if len(open_images) > 2:
        for image in filter(
            lambda x: x != open_images[first_index] and x != open_images[base_index], open_images
        ):
            reg_images.append(f"R_{image}")
            script.append(f"{reg_images[-1]} = Register[0,0,0,0,1](  {image}, {open_images[base_index]}  )")
            script.append(f"Describe({reg_images[-1]})")

    return open_images, reg_images


def stack(image_paths: list[Path], input_dir: Path, output_dir: Path) -> tuple[list[str], list[Path]]:
    total_images: int = len(image_paths)
    """Number of images to stack."""
    num_stacks: int = prompt_int("Enter the total number of stacks to create", 1, total_images // 2)
    """Number of stacks to create."""
    stack_paths: list[Path] = []
    """Paths of stacked output image files."""
    images: list[list[Path]] = []
    """Paths of images in each stack."""
    stack_size: int
    """Size of current stack."""

    script = [
        "# ----------------------------------------------------",
        "# Stacking script generated by runregistar",
        "# ----------------------------------------------------",
        "",
        f'SetDirectory( "{input_dir}" )',
    ]

    if total_images % num_stacks == 0 and prompt_yes_no("Are all stacks equal in size"):
        stack_size = total_images // num_stacks
        images = [image_paths[i : i + stack_size] for i in range(0, total_images, stack_size)]
    else:
        print("Enter the number of images for each individual stack ...")
        assigned_count: int = 0

        for stack_num in range(1, num_stacks):
            max_allowed: int = total_images - assigned_count - (num_stacks - stack_num)
            stack_size = prompt_int(
                f"Enter number of images in stack {stack_num}, first image {image_paths[assigned_count].name} (2 to {max_allowed}): ",
                2,
                max_allowed,
            )
            images.append(image_paths[assigned_count : assigned_count + stack_size])
            assigned_count += stack_size

        # Last stack gets whatever is left over automatically
        stack_size = total_images - assigned_count
        images.append(image_paths[assigned_count : assigned_count + stack_size])
        print(f"Stack {num_stacks} size is {stack_size} (auto-assigned remainder).")

    # Build RegiStar script
    for stack_num, stack_files in enumerate(images, start=1):
        open_images: list[str]
        """List of open image IDs SnnIii, nn = stack number, ii = image number in stack."""

        script.append(f"# --- Processing Stack {stack_num:02d} ---")
        open_images = register(stack_files, script, stack_num)[0]

        combid: str = f"C{stack_num:02d}"
        """Combined image ID."""
        script.append(f"{combid} = Combine[4,1]( {open_images[0]} )")
        script.append(f"Describe({combid})")

        stack_name: str = f"{stack_files[0].stem}-{stack_files[-1].stem}_stacked.tif"
        stack_paths.append(output_dir / stack_name)
        script.append(f'SaveAs( {combid}, "{output_dir / stack_name}" )')
        script.append("CloseAll( )")
        script.append("")

    return script, stack_paths


def main() -> None:

    parser = argparse.ArgumentParser(description="Run StarNet on an input image")
    parser.add_argument(
        "--operation",
        choices=["register", "stack"],
        help="Operation to perform: register, or stack (default: register if two input files, stack otherwise).",
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("input", nargs="+", help="TIFF image input files")

    global ARGS
    ARGS = parser.parse_args()

    print(f"RegiStar Wrapper Version {__version__}")

    for exe_path in REGISTAR_EXECUTABLE_PATHS:
        if os.path.exists(exe_path):
            break
    else:
        raise FileNotFoundError("RegiStar.exe not found in standard paths.")

    image_paths: list[Path] = sorted(
        arg.resolve(strict=True) for arg in file_path_generator(ARGS.input, recursive=False)
    )
    """Paths of image files to process."""

    total_images: int = len(image_paths)
    """Number of images to stack."""
    if total_images < 2:
        raise ValueError(f"At least 2 images are required, only {total_images} provided.")

    input_dir: Path = image_paths[0].parent
    """Path of the image input directory."""
    output_dir: Path = image_paths[0].parent
    """Path of the image output directory."""
    output_images: list[Path] = []
    """List of output image paths."""

    print("Input images:")
    for i, in_path in enumerate(image_paths, 1):
        print(f"  {i:2}. {in_path.name}")
        if not in_path.is_file():
            raise ValueError(f"File not found: {in_path}")
        if in_path.parent != input_dir:
            raise ValueError(f"File not in input directory: {in_path}")

    script: list[str]
    """Generated RegiStar script."""

    if ARGS.operation == "register":
        base_index = prompt_int("Enter the number of the base image: ", 1, len(image_paths), default=1) - 1

        script: list[str] = [
            "# ----------------------------------------------------",
            "# Registration script generated by runregistar",
            "# ----------------------------------------------------",
            "",
            f'SetDirectory( "{input_dir}" )',
        ]

        reg_images: list[str] = register(image_paths, script, base_index=base_index)[1]
        for image, path in zip(reg_images, filter(lambda p: p != image_paths[base_index], image_paths)):
            reg_name = path.stem + "_reg.tif"
            output_images.append(output_dir / reg_name)
            script.append(f'SaveAs( {image}, "{output_images[-1]}" )')
            script.append("CloseAll( )")
            script.append("")

    elif ARGS.operation == "stack":
        script, output_images = stack(image_paths, input_dir, output_dir)

    else:
        raise ValueError(f"Invalid operation: {ARGS.operation}")

    # Write the script file
    output_script_path = output_dir / "auriga_batch_job.txt"
    with open(output_script_path, "w") as f:
        f.write("\n".join(script))

    print(f"RegiStar script generated at: {output_script_path}")

    cmd = [exe_path, "-script", str(output_script_path)]
    print(f"Running RegiStar: {cmd}")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        fatal_error(f"RegiStar failed with return code {result.returncode}")

    print("Output images:")
    for out_path in output_images:
        print(f"  {out_path.name}")
        if not out_path.is_file():
            raise ValueError(f"File not found: {out_path}")


def cli() -> None:
    """Command-line interface."""
    try:
        main()
        cleanup_and_exit(0)

    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(1)

    except Exception as e:  # noqa: BLE001
        fatal_error(str(e))


def register_op() -> None:
    """Insert registration operation in command-line arguments."""
    sys.argv = [sys.argv[0]] + ["--operation", "register"] + sys.argv[1:]
    cli()


def stack_op() -> None:
    """Insert stacking operation in command-line arguments."""
    sys.argv = [sys.argv[0]] + ["--operation", "stack"] + sys.argv[1:]
    cli()


if __name__ == "__main__":
    cli()

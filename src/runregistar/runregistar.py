import argparse
import glob
import os
import subprocess
import sys
from collections import defaultdict
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


class Image(Path):
    """Small wrapper around pathlib.Path for image files."""

    __slots__ = ("_id",)
    _id: str

    def __new__(cls, *args, **kwargs):
        """Create a new Image instance."""
        img = super().__new__(cls, *args, **kwargs)
        img._id = f"ID{id(img):x}"
        """Unique image ID"""
        return img

    def with_segments(self, *segments):
        """
        CRITICAL: Ensures path modifications (.parent, / operator)
        generate a brand new path instance with its own unique object ID.
        """
        return Image(*segments)

    @property
    def id(self) -> str:
        """Return the image file unique ID."""
        return self._id


class Script:
    """Class to represent a RegiStar script."""

    def __init__(self, output_dir: Path):
        """Initialize the Script instance."""
        self.lines: list[str] = []
        """List of lines in the script."""
        self.output_dir: Path = output_dir
        """Path to the output directory for generated images."""
        self.groups: defaultdict[str, list[Image]] = defaultdict(list)
        """Registered image groups, keyed by base image id."""
        self.base_image_ids: list[str] = []
        """IDs of the base images."""

    def comment(self, *lines: str) -> None:
        """Add comment lines to the script.

        Args:
            lines (str): Comment text.
        """
        for line in lines:
            self.lines.append(f"# {line}")

    def set_directory(self, directory: str) -> None:
        """Set the directory for input images.

        Args:
            directory (str): Directory path.
        """
        self.lines.append(f'SetDirectory( "{directory}" )')

    def open_image(self, image: Image) -> None:
        """Open an input image file.

        Args:
            image (Image): Image instance to open.

        Raises:
            FileNotFoundError: If the image file does not exist.
        """
        if not image.is_file():
            raise FileNotFoundError(f"Image file not found: {image}")

        self.lines.append(f'{image.id} = Open( "{image!s}" )')
        self.lines.append(f"Describe({image.id})")
        self.groups[image.id].append(image)

    def register_images(self, base_image: Image, images_to_register: list[Image]) -> None:
        """Register a list of images to a base image.

        Args:
            base_image (Image): Base image for registration.
            images_to_register (list[Image]): List of images to register.
        Note:
            Images are registered to Match the dimensions of the base image.
        """
        self.base_image_ids.append(base_image.id)
        for image in images_to_register:
            self.open_image(image)
            if image.id != base_image.id:
                reg_image: Image = Image(self.output_dir / f"{image.stem}_reg.tif")
                self.groups[base_image.id].append(reg_image)
                self.lines.append(
                    f"{reg_image.id} = Register[0,0,0,0,1]( {image.id}, {base_image.id} )"
                )
                self.lines.append(f"Describe({reg_image.id})")

    def stack_images(self, images: list[Image]) -> Image:
        """Stack a list of images into a single output image.

        Args:
            images (list[Image]): List of images to stack.
        Returns:
            Image: Stacked Image.
        Note:
            Images are Combined using the Median/Mean function and Intersection of dimensions.
        """
        stack_image: Image = Image(self.output_dir / f"{images[0].stem}-{images[-1].stem}_stk.tif")
        """Stacked image."""
        self.register_images(images[0], images)
        self.groups[images[0].id].append(stack_image)
        self.lines.append(f"{stack_image.id} = Combine[4,1]( {images[0].id} )")
        self.lines.append(f"Describe({stack_image.id})")
        return stack_image

    def save_image(self, image: Image) -> None:
        """Save an image to the output directory.

        Args:
            image (Image): Image instance to save.
        """
        self.lines.append(f'SaveAs( {image.id}, "{image!s}" )')

    def close_all(self) -> None:
        """Close all open images."""
        self.lines.append("CloseAll( )")

    def execute(self, exe_path: str) -> None:
        """Execute the script using the RegiStar executable.

        Args:
            exe_path (str): Path to the RegiStar executable.
        """
        output_script_path: Path = self.output_dir / "auriga_registar_script.txt"
        with open(output_script_path, "w") as f:
            f.write("\n".join(self.lines))
        print(f"Auriga RegiStar script generated at: {output_script_path}")

        cmd = [exe_path, "-script", str(output_script_path)]
        print(f"Running RegiStar: {cmd}")
        subprocess.run(cmd, check=True)

    def output_images(self, operation: str) -> list[Image]:
        """Return a list of output images based on the operation performed.

        Args:
            operation (str): The operation performed, either "register" or "stack".
        """
        output_images: list[Image] = []
        """Registered or stacked images, depending on the operation."""
        tag = "_reg" if operation == "register" else "_stk"
        output_images = [
            image
            for base_id in self.base_image_ids
            for image in self.groups[base_id]
            if image.stem[-4:] == tag
        ]
        return output_images


def cleanup_and_exit(status: int = 0) -> NoReturn:
    """Clean up and exit with the given status code.

    Args:
        status (int): Exit status code. Defaults to 0.
    """
    print(f"{SCRIPT_NAME} finished.")
    input("Press Enter to exit ...")

    sys.exit(status)


def fatal_error(msg: str) -> NoReturn:
    """Print a CRITICAL message and sys.exit(1).

    Args:
        msg (str): Error message to display.
    """
    print(f"CRITICAL - {msg}; exiting.", file=sys.stderr)
    cleanup_and_exit(1)


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


def stack(input_images: list[Image], script: Script) -> None:
    """Stack input images into multiple stacks based on user input.

    Args:
        input_images (list[Image]): List of input images to stack.
        script (Script): RegiStar Script instance.

    """
    total_images: int = len(input_images)
    """Number of images to stack."""
    num_stacks: int = (
        1
        if total_images <= 3
        else prompt_int("Enter the total number of stacks to create", 1, total_images // 2)
    )
    """Number of stacks to create."""
    images: list[list[Image]] = []
    """Input images in each stack."""
    stack_size: int
    """Size of current stack."""

    if num_stacks == 1:
        images.append(input_images)
    elif total_images % num_stacks == 0 and prompt_yes_no("Are all stacks equal in size"):
        stack_size = total_images // num_stacks
        images = [input_images[i : i + stack_size] for i in range(0, total_images, stack_size)]
    else:
        print("Enter the number of images for each individual stack ...")
        assigned_count: int = 0

        for stack_num in range(1, num_stacks):
            max_allowed: int = total_images - assigned_count - (num_stacks - stack_num)
            stack_size = prompt_int(
                f"Enter number of images in stack {stack_num}, first image {input_images[assigned_count].name} (2 to {max_allowed}): ",
                2,
                max_allowed,
            )
            images.append(input_images[assigned_count : assigned_count + stack_size])
            assigned_count += stack_size

        # Last stack gets whatever is left over automatically
        stack_size = total_images - assigned_count
        images.append(input_images[assigned_count : assigned_count + stack_size])
        print(f"Stack {num_stacks} size is {stack_size} (auto-assigned remainder).")

    # Build RegiStar script
    for stack_num, stack_images in enumerate(images, start=1):
        script.comment(f"--- Processing Stack {stack_num} ---")
        combined_image = script.stack_images(stack_images)
        script.save_image(combined_image)
        script.close_all()
        script.comment(f"--- Stack {stack_num} processed ---")

    script.comment("----------------------------------------------------")


def main() -> None:
    """Main function to parse arguments and execute the appropriate operation.

    Raises:
        FileNotFoundError: If RegiStar executable is not found.
        ValueError: If invalid operation is specified or insufficient images are provided.
    """
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

    input_images: list[Image] = sorted(
        Image(arg.resolve(strict=True)) for arg in file_path_generator(ARGS.input, recursive=False)
    )
    """List of input images."""

    total_images: int = len(input_images)
    """Number of images to stack."""
    if total_images < 2:
        raise ValueError(f"At least 2 images are required, only {total_images} provided.")

    input_dir: Path = input_images[0].parent
    """Path of the image input directory."""
    output_dir: Path = input_images[0].parent
    """Path of the image output directory."""
    output_images: list[Image] = []
    """List of output image paths."""
    script: Script = Script(output_dir)
    """Generated RegiStar script."""

    script.comment(
        "----------------------------------------------------",
        "Auriga RegiStar script generated by runregistar",
        "----------------------------------------------------",
    )
    script.set_directory(str(input_dir))

    print("Input images:")
    for i, in_path in enumerate(input_images, 1):
        print(f"  {i:2}. {in_path.name}")
        if not in_path.is_file():
            raise ValueError(f"File not found: {in_path}")
        if in_path.parent != input_dir:
            raise ValueError(f"File not in input directory: {in_path}")

    if ARGS.operation == "register":
        base_index = (
            prompt_int("Enter the number of the base image: ", 1, len(input_images), default=1) - 1
        )
        base_image: Image = input_images[base_index]
        script.register_images(base_image, input_images)
        for image in script.groups[base_image.id]:
            if image.stem[-4:] == "_reg":
                script.save_image(image)
        script.close_all()
        script.comment("----------------------------------------------------")

    elif ARGS.operation == "stack":
        stack(input_images, script)

    else:
        raise ValueError(f"Invalid operation: {ARGS.operation}")

    output_images = script.output_images(ARGS.operation)
    existing_output_files = [img for img in output_images if img.is_file()]
    if existing_output_files:
        print("The following output files already exist:")
        for out_path in existing_output_files:
            print(f"  {out_path.name}")
        if not prompt_yes_no("Overwrite existing files?", default=False):
            raise ValueError("Operation cancelled.")

    script.execute(exe_path)

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
    """Insert registration operation in command line arguments."""
    sys.argv = [sys.argv[0]] + ["--operation", "register"] + sys.argv[1:]
    cli()


def stack_op() -> None:
    """Insert stacking operation in command line arguments."""
    sys.argv = [sys.argv[0]] + ["--operation", "stack"] + sys.argv[1:]
    cli()


if __name__ == "__main__":
    cli()

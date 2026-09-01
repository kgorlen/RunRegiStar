<!--
Markdown Guide: https://www.markdownguide.org/basic-syntax/
-->
<!--
Disable markdownlint errors:
fenced-code-language MD040
no-inline-html MD033
-->
<!-- markdownlint-disable MD040 MD033-->

# Run RegiStar

Run RegiStar from Lightroom Classic or as a command.

## Overview

This script wraps the Auriga Imaging RegiStar application so it can be run from
the command line or as an Additional External Editor or Export Post-Processing
application from Adobe Lightroom Classic. It prompts for the base image in
registration mode and for the stack layout in stacking mode, then generates a
RegiStar script and executes it.

It produces:

- registered output images with names ending in `_reg.tif`
- stacked output images with names ending in `_stk.tif`

The script validates input files, enforces a single directory for inputs, and
prompts for stack sizes and the base image when needed.

## Install Python

See [Python](https://www.python.org/downloads/).

## Install pipx

See [pipx](https://pypi.org/project/pipx/).

## Install RegiStar

See the [Auriga Imaging RegiStar](https://aurigaimaging.com/) product page.

## Install runregistar

```
pipx install git+https://github.com/kgorlen/RunRegiStar.git
```

## Configure Adobe Lightroom Classic

### *Edit -> Preferences -> External Editing -> Additional External Editor*

Preset: RegiStar (Register)  
Application: runregistar-reg.exe  
File Format: TIFF  
Template: Filename  

reset: RegiStar (Stack)  
Application: runregistar-stack.exe  
File Format: TIFF  
Template: Filename  

### *File -> Export -> RegiStar (Stack)*

#### File Settings

Image Format: TIFF  
Compression: None  
Color SApace: sRGB IEC61966-2.1  

#### Post-Processing

After Export: Open in Other Application...  
Application: `C:\Users\`*Username*`\.local\bin\runregistar-stack.exe`  

## Usage

**runregistar** [**-h** | **--help** ] [**-v** | **--version**]
**--operation** **register** | **stack** *infile* *infile* [*infile* ...]

**runregistar-reg** [**-h** | **--help** ] [**-v** | **--version**]
*infile* *infile* [*infile* ...]

**runregistar-stack** [**-h** | **--help** ] [**-v** | **--version**]
*infile* *infile* [*infile* ...]

### Positional arguments

*infile*
:   Two or more TIFF image input files in the same directory

### Options

**-h, --help**
:   show this help message and exit

**--operation**
:   **register** or **stack**

**-v, --version**
:   show program version and exit

## Workflow

### Register images

1. Run `runregistar-reg` with two or more TIFF files in the same folder.
2. Choose the base image when prompted.
3. The script generates a RegiStar script and executes it.
4. Registered images are saved with the `_reg.tif` suffix.

### Stack images

1. Run `runregistar-stack` with two or more TIFF files in the same folder.
2. Enter the total number of stacks to create.
3. Enter the number of images for each stack when prompted.
4. The script generates the RegiStar combine operations and saves stacked files
   with the `_stk.tif` suffix.

## Requirements

- Python 3.12 or newer
- Auriga Imaging RegiStar installed on the system

## License

GNU General Public License v3.0 or later. See [LICENSE.txt](LICENSE.txt) for details.

## See Also

- [Auriga Imaging RegiStar](https://aurigaimaging.com/)
- [RunRegiStar Repository](https://github.com/kgorlen/RunRegiStar)

## Author

Keith Gorlen (<kgorlen@gmail.com>)

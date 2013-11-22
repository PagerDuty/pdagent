
# PyDev Setup

PyDev setup notes for OS X 10.8 (Mountain Lion).

## Install Eclipse + PyDev

Since PyDev 3 requires Java 7, and Mountain Lion ships with Java 6, I
installed older versions of Eclipse & PyDev as follows:

- Download newest Eclipse 3.6 from http://wiki.eclipse.org/Older_Versions_Of_Eclipse
  (Eclipse IDE for Java Developers)
- Download newest PyDev 2.X from http://sourceforge.net/projects/pydev/files/pydev/
- Unzip Eclipse
- Unzip PyDev & move into `eclipse/dropins` folder


## Configuration

- Open Eclipse & choose a workspace e.g. `~/Documents/workspace-pydev`

- Open Prefences and apply the following settings:

    - In the section: General -> Editors -> Text Editors
        - Check *Insert spaces for tabs*
        - Set *Print margin column* to 100
        - Optional: check *Show print margin*
        - Optional: check *Show line numbers*

    - In the section: Pydev -> Interpreter - Python
        - Use *Auto Config* to get the default Python interpreter

    - In the section: Pydev -> Editor -> Code Style -> Code Formatter
        - Check *Right trim lines?*

    - In the section: Pydev -> Editor -> Typing
        - Uncheck *After '(' indent to its level ...*

    - In the section: Pydev -> Editor -> Code Analysis
        - Go to tab pep8.py
        - Change Pep8 from "Don't run" to "warning"

    - Optional: In the section: Pydev -> Editor
        - Under *Appearance color options*, choose *Comments*
        - Change the color to a darker grey (or other color)


## Project Setup

- Open the Pydev perspective

- Choose menu: File -> Import -> Existing projects into workspace

- Choose the project directory

- When editing, use Format Code and Organize Imports for consistent formatting

    > TIP: Organize imports should not be used in some cases, especially python
    > files which modify sys.path before import.



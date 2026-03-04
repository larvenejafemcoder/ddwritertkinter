# dd image writer

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Discord](https://img.shields.io/discord/1477694881127469202?style=flat\&logo=https%3A%2F%2Fcdn.discordapp.com%2Ficons%2F1477694881127469202%2F1b2c4e8defc9220de11098108fa1ed81.webp%3Fsize%3D256\&logoColor=rgb\&label=Join%20Server\&link=https%3A%2F%2Fdiscord.gg%2FTMnXwezsyV)
![Status: Beta](https://img.shields.io/badge/status-beta-orange)

## Beta Release

**dd image writer** is currently in **Beta**.

It's a physical drive imaging utility written in Python - actually a **`dd` image writer with a GUI**. Think of it as a frontend for `dd` that helps you write disk images to USB drives safely.

While core functionality is being implemented and refined, the project is still under active development. Users should expect bugs, incomplete features, and ongoing structural changes.

If you rely on stable, production-grade imaging tools, consider established alternatives until dd image writer reaches a stable release.

## What it actually does

dd image writer is a graphical wrapper around `dd` (the classic Unix disk duplicator) that:

- **Discovers USB devices** on your system
- **Writes image files** (ISO, IMG, etc.) to USB drives using `dd`
- **Validates ISO signatures** before writing (optional but recommended)
- **Checks SHA256 hashes** to verify image integrity
- **Formats USB drives** with various filesystems (FAT32, exFAT, NTFS, ext4)
- **Shows detailed drive info** so you know exactly what you're writing to

## Quick start (for beginners)

This section is written for people who are **new to Python and Git** and just want to **see the app run** on Linux.

## Current prototype: Tkinter (single file)

The current prototype GUI is a **single, standalone file**:

- `tkinter_gui/main.py`
- It uses **Tkinter (built-in)** plus common Linux tools:
  - USB discovery: `/proc/mounts`, `/sys`, `lsblk`
  - Writing images: `dd` (the real workhorse)
  - Formatting/labeling: `pkexec` + `mkfs.*` + label tools

### 1. Install the basics (once)

- **Python 3.10 or newer**
  - On most modern distros, you can check with:
    
    ```bash
    python3 --version
    ```
  - If it says something like `Python 3.10.x` or higher, you are good.
  - If you get "command not found", install Python via your distro's package manager (examples):
    - Ubuntu/Debian:
      
      ```bash
      sudo apt update
      sudo apt install python3 python3-venv python3-pip git
      ```
    - Fedora:
      
      ```bash
      sudo dnf install python3 python3-venv python3-pip git
      ```
    - Arch/Manjaro:
      
      ```bash
      sudo pacman -Syu python python-virtualenv python-pip git
      ```

- **Git**
  - If you ran one of the commands above with `git` included, you can skip this.
  - To check quickly:
    
    ```bash
    git --version
    ```

### 2. Download the project (clone the repo)

1. Open a terminal.
2. Choose a folder where you want the project (for example your home directory):
   
   ```bash
   cd ~
   ```
3. Download the code:
   
   ```bash
   git clone https://github.com/hog185/rufus-py.git
   cd rufus-py
   ```

At this point you should see files like `README.md`, a `tkinter_gui` folder, and a `src` folder if you run:

```bash
ls
```

### 3. Create and activate a virtual environment (recommended)

This step keeps dd image writer's Python packages separate from the rest of your system.

1. **Create** the virtual environment (only once per clone):
   
   ```bash
   python3 -m venv .venv
   ```

2. **Activate** it (you must do this in every new terminal before running the app):
   - If you use Bash, Zsh, or most common shells:
     
     ```bash
     source .venv/bin/activate
     ```

   - After activation, your prompt will usually show `(.venv)` at the beginning.

3. To **deactivate** later (leave the venv), you can run:
   
   ```bash
   deactivate
   ```

### 4. Install the Python dependencies

For the **Tkinter prototype** (`tkinter_gui/main.py`), there are **no required pip dependencies** (Tkinter is part of the standard library).

The **system tools** below are required for some features:

- **Always used**
  - `lsblk` (usually from `util-linux`)
  - `dd` (usually from `coreutils`)
- **Required for Format / Label buttons**
  - `pkexec` (Polkit) for privilege prompts
  - Filesystem tools (install what you need):
    - FAT32: `mkfs.vfat`, `fatlabel` (often `dosfstools`)
    - exFAT: `mkfs.exfat` (often `exfatprogs`)
    - NTFS: `mkfs.ntfs`, `ntfslabel` (often `ntfs-3g`)
    - ext4: `mkfs.ext4`, `e2label` (often `e2fsprogs`)

### 5. Run the application (safe, visual test)

For a quick, safe test that just shows the **Tkinter prototype GUI**:

```bash
python tkinter_gui/main.py
```

What should happen:

- A terminal message prints something like:
  
  ```text
  Detected USB devices: {...}
  ```
- A window titled **"dd image writer (Tkinder prototype)"** opens.
- If you have USB sticks plugged in, they should appear in the **Device** dropdown.

In this basic test you **do not need to actually write to a USB device**. You can just:

- Click **Refresh** to re-detect USB devices
- Click **USB Info** / **Check ISO signature** / **Check SHA**
- Close the window when you are done

### 6. What each button does (Tkinter prototype)

- **Refresh**: re-detect USB devices under `/media` and `/run/media`
- **USB Info**: shows `device_node`, `label`, and `mount_path`
- **Check ISO signature**: validates ISO9660 Primary Volume Descriptor (sector 16)
- **Check SHA**: compares SHA256 of the selected image to the expected value
- **Write image (dd)**: writes the selected image file to the selected USB device using `dd`
  - Checkbox **Validate ISO signature before dd**:
    - **ON** (recommended for `.iso`): refuses to write if ISO signature check fails
    - **OFF** (for `.img`/raw images): writes any file without ISO signature validation
- **Format**: formats the selected device using `pkexec` + `mkfs.*` (destructive)
- **Set label**: unmounts, sets label using `pkexec` + label tool, then mounts again
- **Cluster info**: reads sizes via `pkexec blockdev` and shows computed values

### 7. Important safety notes before real USB writing

dd image writer is a **drive imaging tool**. Some actions are **destructive**:

- **Write image (dd)** will overwrite the entire target device.
- **Format** will erase data on the target device.

Before clicking destructive actions:

- **Double-check the selected device** in the **Device** dropdown.
- Be absolutely sure it is your USB stick and **not** another drive.
- If unsure, use **USB Info** first and confirm the `device_node`.

For quick testing, it is perfectly fine to **open the window and explore the UI** without writing to any real USB drive.

### 8. Exiting and cleaning up

- To **close the app**, just close the window.
- To **leave the virtual environment**:
  
  ```bash
  deactivate
  ```
- To remove the project entirely:
  - Make sure the venv is deactivated.
  - Delete the `rufus-py` folder:
    
    ```bash
    rm -rf ~/rufus-py
    ```
